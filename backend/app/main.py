from io import BytesIO

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


@app.post("/api/fact-check", response_model=FactCheckReport)
async def fact_check(
    scan_mode: ScanMode = Form(ScanMode.focused),
    file: UploadFile = File(...),
) -> FactCheckReport:
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
        raise HTTPException(
            status_code=502,
            detail="Verification service failed. Please try again.",
        ) from exc
