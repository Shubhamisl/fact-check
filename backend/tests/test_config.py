import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings


def test_settings_defaults_are_assignment_safe():
    settings = Settings(
        openrouter_api_key="or-key",
        tavily_api_key="tv-key",
    )

    assert settings.openrouter_model == "openai/gpt-4o-mini"
    assert settings.openrouter_vision_model == "openai/gpt-4o-mini"
    assert settings.max_claims_focused == 12
    assert settings.max_claims_deep == 25
    assert settings.max_ocr_pages == 5
    assert settings.max_pdf_size_mb == 10
    assert settings.tavily_search_depth == "basic"
    assert settings.frontend_origin == "http://localhost:5173"
    assert settings.has_required_keys is True


def test_settings_exposes_configured_limits():
    settings = Settings(
        openrouter_api_key="or-key",
        tavily_api_key="tv-key",
        max_claims_focused=3,
        max_claims_deep=8,
        max_ocr_pages=2,
        max_pdf_size_mb=4,
    )

    assert settings.claim_limit_for_mode("focused") == 3
    assert settings.claim_limit_for_mode("deep") == 8
    assert settings.max_pdf_size_bytes == 4 * 1024 * 1024


def test_settings_reports_missing_required_keys():
    settings = Settings()

    assert settings.has_required_keys is False
