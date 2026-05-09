import sys
from time import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main
from app.models import PageText


class FakeRunningTask:
    def __init__(self) -> None:
        self.cancelled = False

    def done(self) -> bool:
        return False

    def cancel(self) -> None:
        self.cancelled = True


@pytest.fixture
def client() -> TestClient:
    return TestClient(main.app, raise_server_exceptions=False)


@pytest.fixture
def configured_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main.settings, "openrouter_api_key", "openrouter-key")
    monkeypatch.setattr(main.settings, "tavily_api_key", "tavily-key")


def test_health_returns_status_and_configuration_flag(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "configured" in payload


def test_fact_check_rejects_non_pdf_upload(client: TestClient) -> None:
    response = client.post(
        "/api/fact-check",
        data={"scan_mode": "focused"},
        files={"file": ("notes.txt", b"not a pdf", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Please upload a PDF file."


def test_fact_check_rejects_invalid_pdf_bytes(
    client: TestClient,
    configured_settings: None,
) -> None:
    response = client.post(
        "/api/fact-check",
        data={"scan_mode": "focused"},
        files={"file": ("file.pdf", b"not a pdf", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Could not read this PDF file."


def test_fact_check_rejects_missing_provider_keys(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main.settings, "openrouter_api_key", "")
    monkeypatch.setattr(main.settings, "tavily_api_key", "")

    response = client.post(
        "/api/fact-check",
        data={"scan_mode": "focused"},
        files={"file": ("file.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 503
    assert (
        response.json()["detail"]
        == "OpenRouter and Tavily API keys are not configured."
    )


def test_fact_check_rejects_oversized_pdf(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main.settings, "max_pdf_size_mb", 1)

    response = client.post(
        "/api/fact-check",
        data={"scan_mode": "focused"},
        files={"file": ("file.pdf", b"0" * (1024 * 1024 + 1), "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "PDF must be 1 MB or smaller."


def test_fact_check_translates_orchestrator_failure(
    client: TestClient,
    configured_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingOrchestrator:
        async def run(self, file_name, pages, scan_mode):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        main,
        "extract_pdf_pages",
        lambda file_obj: [PageText(page_number=1, text="A checkable claim.", source="pdf")],
    )
    monkeypatch.setattr(main, "find_pages_needing_ocr", lambda pages: [])
    monkeypatch.setattr(main, "build_orchestrator", lambda: FailingOrchestrator())

    response = client.post(
        "/api/fact-check",
        data={"scan_mode": "focused"},
        files={"file": ("file.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Verification service failed. Please try again."


def test_fact_check_debug_errors_include_provider_detail(
    client: TestClient,
    configured_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingOrchestrator:
        async def run(self, file_name, pages, scan_mode):
            raise RuntimeError("model does not support response_format")

    monkeypatch.setattr(main.settings, "debug_errors", True)
    monkeypatch.setattr(
        main,
        "extract_pdf_pages",
        lambda file_obj: [PageText(page_number=1, text="A checkable claim.", source="pdf")],
    )
    monkeypatch.setattr(main, "find_pages_needing_ocr", lambda pages: [])
    monkeypatch.setattr(main, "build_orchestrator", lambda: FailingOrchestrator())

    response = client.post(
        "/api/fact-check",
        data={"scan_mode": "focused"},
        files={"file": ("file.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["message"] == "Verification service failed. Please try again."
    assert detail["debug"]["type"] == "RuntimeError"
    assert detail["debug"]["message"] == "model does not support response_format"
    monkeypatch.setattr(main.settings, "debug_errors", False)


def test_cleanup_jobs_does_not_evict_running_jobs_when_store_is_full() -> None:
    main.jobs.clear()
    main.job_tasks.clear()
    running_task = FakeRunningTask()
    now = time()

    try:
        main.jobs["running-job"] = {
            "job_id": "running-job",
            "status": "running",
            "progress": 20,
            "updated_at": now - 10,
        }
        main.job_tasks["running-job"] = running_task
        for index in range(main.MAX_JOBS):
            job_id = f"complete-job-{index}"
            main.jobs[job_id] = {
                "job_id": job_id,
                "status": "complete",
                "progress": 100,
                "updated_at": now + index,
            }

        main.cleanup_jobs()

        assert "running-job" in main.jobs
        assert running_task.cancelled is False
        assert len(main.jobs) == main.MAX_JOBS
    finally:
        main.jobs.clear()
        main.job_tasks.clear()
