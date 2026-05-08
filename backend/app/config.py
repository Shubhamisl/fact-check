from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )

    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="openai/gpt-4o-mini", alias="OPENROUTER_MODEL")
    openrouter_vision_model: str = Field(
        default="openai/gpt-4o-mini",
        alias="OPENROUTER_VISION_MODEL",
    )
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    max_claims_focused: int = Field(default=12, alias="MAX_CLAIMS_FOCUSED")
    max_claims_deep: int = Field(default=25, alias="MAX_CLAIMS_DEEP")
    max_ocr_pages: int = Field(default=5, alias="MAX_OCR_PAGES")
    max_pdf_size_mb: int = Field(default=10, alias="MAX_PDF_SIZE_MB")
    tavily_search_depth: str = Field(default="basic", alias="TAVILY_SEARCH_DEPTH")
    frontend_origin: str = Field(
        default="http://localhost:5173",
        alias="FRONTEND_ORIGIN",
    )

    @property
    def max_pdf_size_bytes(self) -> int:
        return self.max_pdf_size_mb * 1024 * 1024

    @property
    def has_required_keys(self) -> bool:
        return bool(self.openrouter_api_key and self.tavily_api_key)

    def claim_limit_for_mode(self, mode: str) -> int:
        if mode == "deep":
            return self.max_claims_deep
        return self.max_claims_focused


@lru_cache
def get_settings() -> Settings:
    return Settings()
