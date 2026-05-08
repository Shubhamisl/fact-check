from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="openai/gpt-4o-mini", alias="OPENROUTER_MODEL")
    openrouter_vision_model: str = Field(
        default="openai/gpt-4o-mini",
        alias="OPENROUTER_VISION_MODEL",
    )
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    max_claims_focused: int = Field(default=12, alias="MAX_CLAIMS_FOCUSED", gt=0)
    max_claims_deep: int = Field(default=25, alias="MAX_CLAIMS_DEEP", gt=0)
    max_ocr_pages: int = Field(default=5, alias="MAX_OCR_PAGES", gt=0)
    max_pdf_size_mb: int = Field(default=10, alias="MAX_PDF_SIZE_MB", gt=0)
    max_search_queries_per_group: int = Field(
        default=2,
        alias="MAX_SEARCH_QUERIES_PER_GROUP",
        gt=0,
    )
    max_search_results_per_query: int = Field(
        default=2,
        alias="MAX_SEARCH_RESULTS_PER_QUERY",
        gt=0,
    )
    enable_follow_up_search: bool = Field(default=False, alias="ENABLE_FOLLOW_UP_SEARCH")
    tavily_search_depth: str = Field(default="basic", alias="TAVILY_SEARCH_DEPTH")
    frontend_origin: str = Field(
        default="http://localhost:5173",
        alias="FRONTEND_ORIGIN",
    )
    debug_errors: bool = Field(default=False, alias="DEBUG_ERRORS")

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
