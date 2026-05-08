import asyncio
from io import BytesIO
from time import time
from traceback import format_exception_only
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models import EvidenceSource, ExtractedClaim, FactCheckReport, ScanMode
from app.services.claim_extractor import ClaimExtractor
from app.services.ocr_service import OcrService
from app.services.openrouter_client import OpenRouterClient
from app.services.orchestrator import FactCheckOrchestrator
from app.services.pdf_service import extract_pdf_pages, find_pages_needing_ocr
from app.services.search_service import (
    gather_evidence_for_group,
    normalize_tavily_results,
)
from app.services.tavily_client import TavilyClient
from app.services.verifier import Verifier

settings = get_settings()

# MVP job store for a single Render web service process. Jobs are not durable and
# are not shared across multiple workers; keep Render configured accordingly until
# this moves to a real queue/store.
JOB_TTL_SECONDS = 30 * 60
MAX_JOBS = 100
jobs: dict[str, dict[str, object]] = {}
job_tasks: dict[str, asyncio.Task[None]] = {}

app = FastAPI(title="Fact-Check Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "configured": settings.has_required_keys,
        "openrouter_model": settings.openrouter_model,
        "openrouter_vision_model": settings.openrouter_vision_model,
        "tavily_search_depth": settings.tavily_search_depth,
    }


class LiveSearchService:
    def __init__(self, tavily_client: TavilyClient) -> None:
        self.tavily_client = tavily_client

    async def gather_evidence_for_group(
        self,
        topic: str,
        claims: list[ExtractedClaim],
    ) -> list[EvidenceSource]:
        return await gather_evidence_for_group(self.tavily_client, topic, claims)

    async def follow_up(self, claim: ExtractedClaim) -> list[EvidenceSource]:
        query = f"{claim.text} latest official source correction"
        raw = await self.tavily_client.search(query, max_results=5)
        return normalize_tavily_results(raw, query)


def build_orchestrator() -> FactCheckOrchestrator:
    openrouter_client = OpenRouterClient()
    tavily_client = TavilyClient(
        api_key=settings.tavily_api_key,
        search_depth=settings.tavily_search_depth,
    )
    return FactCheckOrchestrator(
        claim_extractor=ClaimExtractor(openrouter_client),
        search_service=LiveSearchService(tavily_client),
        verifier=Verifier(openrouter_client),
        settings=settings,
    )


def update_job(job_id: str, values: dict[str, object]) -> bool:
    job = jobs.get(job_id)
    if not job:
        return False

    job.update(values)
    job["updated_at"] = time()
    return True


def remove_job(job_id: str, cancel_task: bool = False) -> bool:
    task = job_tasks.pop(job_id, None)
    if cancel_task and task and not task.done():
        task.cancel()

    return jobs.pop(job_id, None) is not None


def cleanup_jobs() -> None:
    now = time()
    stale_job_ids = [
        job_id
        for job_id, job in jobs.items()
        if now - float(job.get("updated_at", 0)) > JOB_TTL_SECONDS
    ]
    for job_id in stale_job_ids:
        remove_job(job_id, cancel_task=True)

    excess_count = len(jobs) - MAX_JOBS
    if excess_count <= 0:
        return

    oldest_job_ids = sorted(
        jobs,
        key=lambda current_job_id: float(jobs[current_job_id].get("updated_at", 0)),
    )
    for job_id in oldest_job_ids[:excess_count]:
        remove_job(job_id, cancel_task=True)


def provider_error_detail(exc: Exception) -> dict[str, str]:
    detail = {
        "type": exc.__class__.__name__,
        "message": str(exc) or "".join(format_exception_only(type(exc), exc)).strip(),
    }
    cause = exc.__cause__ or exc.__context__
    if cause:
        detail["cause_type"] = cause.__class__.__name__
        detail["cause_message"] = str(cause)
    return detail


def verification_failure_payload(exc: Exception) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "failed",
        "progress": 100,
        "error": "Verification service failed. Please try again.",
    }
    if settings.debug_errors:
        payload["error_details"] = provider_error_detail(exc)
    return payload


def http_exception_failure_payload(exc: HTTPException) -> dict[str, object]:
    if isinstance(exc.detail, dict):
        message = exc.detail.get("message") or "Verification service failed. Please try again."
        payload: dict[str, object] = {
            "status": "failed",
            "progress": 100,
            "error": message,
        }
        if settings.debug_errors and "debug" in exc.detail:
            payload["error_details"] = exc.detail["debug"]
        return payload

    return {
        "status": "failed",
        "progress": 100,
        "error": exc.detail,
    }


async def read_valid_pdf_upload(file: UploadFile) -> tuple[str, bytes]:
    file_name = file.filename or ""
    is_pdf_content = file.content_type == "application/pdf"
    is_pdf_name = file_name.lower().endswith(".pdf")
    if not is_pdf_content and not is_pdf_name:
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > settings.max_pdf_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"PDF must be {settings.max_pdf_size_mb} MB or smaller.",
        )

    if not settings.has_required_keys:
        raise HTTPException(
            status_code=503,
            detail="OpenRouter and Tavily API keys are not configured.",
        )

    return file_name, pdf_bytes


async def build_fact_check_report(
    file_name: str,
    pdf_bytes: bytes,
    scan_mode: ScanMode,
) -> FactCheckReport:
    try:
        pages = extract_pdf_pages(BytesIO(pdf_bytes))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Could not read this PDF file.",
        ) from exc

    pages_needing_ocr = find_pages_needing_ocr(pages)

    if pages_needing_ocr:
        try:
            openrouter_client = OpenRouterClient()
            ocr_service = OcrService(openrouter_client)
            ocr_pages = await ocr_service.extract_pages(pdf_bytes, pages_needing_ocr)
        except HTTPException:
            raise
        except Exception as exc:
            if settings.debug_errors:
                detail = {
                    "message": "Verification service failed. Please try again.",
                    "debug": provider_error_detail(exc),
                }
                raise HTTPException(status_code=502, detail=detail) from exc
            raise HTTPException(
                status_code=502,
                detail="Verification service failed. Please try again.",
            ) from exc

        ocr_by_page = {page.page_number: page for page in ocr_pages}
        pages = [
            ocr_by_page[page.page_number]
            if (
                page.page_number in ocr_by_page
                and len(ocr_by_page[page.page_number].text.strip())
                > len(page.text.strip())
            )
            else page
            for page in pages
        ]

    if not any(page.text.strip() for page in pages):
        raise HTTPException(
            status_code=422,
            detail="No extractable text found in this PDF.",
        )

    try:
        orchestrator = build_orchestrator()
        return await orchestrator.run(file_name, pages, scan_mode)
    except HTTPException:
        raise
    except Exception as exc:
        if settings.debug_errors:
            detail = {
                "message": "Verification service failed. Please try again.",
                "debug": provider_error_detail(exc),
            }
            raise HTTPException(status_code=502, detail=detail) from exc
        raise HTTPException(
            status_code=502,
            detail="Verification service failed. Please try again.",
        ) from exc


async def run_job(
    job_id: str,
    file_name: str,
    pdf_bytes: bytes,
    scan_mode: ScanMode,
) -> None:
    if not update_job(job_id, {"status": "running", "progress": 5}):
        return

    try:
        update_job(job_id, {"progress": 20})
        report = await build_fact_check_report(file_name, pdf_bytes, scan_mode)
    except HTTPException as exc:
        update_job(job_id, http_exception_failure_payload(exc))
    except Exception as exc:
        update_job(job_id, verification_failure_payload(exc))
    else:
        update_job(
            job_id,
            {
                "status": "complete",
                "progress": 100,
                "report": report.model_dump(mode="json"),
            }
        )
    finally:
        job_tasks.pop(job_id, None)


@app.post("/api/fact-check", response_model=FactCheckReport)
async def fact_check(
    scan_mode: ScanMode = Form(ScanMode.focused),
    file: UploadFile = File(...),
) -> FactCheckReport:
    file_name, pdf_bytes = await read_valid_pdf_upload(file)
    return await build_fact_check_report(file_name, pdf_bytes, scan_mode)


@app.post("/api/jobs")
async def create_job(
    scan_mode: ScanMode = Form(ScanMode.focused),
    file: UploadFile = File(...),
) -> dict[str, str]:
    cleanup_jobs()
    file_name, pdf_bytes = await read_valid_pdf_upload(file)
    job_id = str(uuid4())
    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "file_name": file_name,
        "updated_at": time(),
    }
    job_tasks[job_id] = asyncio.create_task(
        run_job(job_id, file_name, pdf_bytes, scan_mode)
    )
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, object]:
    cleanup_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str) -> dict[str, str]:
    cleanup_jobs()
    if not remove_job(job_id, cancel_task=True):
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"status": "deleted"}
