import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main
from app.models import PageText


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
