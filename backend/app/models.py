from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class ScanMode(str, Enum):
    focused = "focused"
    deep = "deep"


VerdictLabel = Literal["Verified", "Inaccurate", "False / Unsupported"]
ConfidenceLabel = Literal["High", "Medium", "Low"]


class PageText(BaseModel):
    page_number: int
    text: str
    source: Literal["pdf", "ocr"]


class ExtractedClaim(BaseModel):
    id: str
    text: str
    page_number: int | None = None
    claim_type: str
    topic: str
    importance: Literal["high", "medium", "low"] = "medium"


class EvidenceSource(BaseModel):
    title: str
    url: HttpUrl
    snippet: str
    published_date: str | None = None
    query: str


class ClaimVerdict(BaseModel):
    claim: ExtractedClaim
    verdict: VerdictLabel
    corrected_fact: str | None = None
    confidence: ConfidenceLabel
    reasoning: str
    sources: list[EvidenceSource] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)


class FactCheckReport(BaseModel):
    file_name: str
    scan_mode: ScanMode
    summary: dict[str, int]
    claims: list[ClaimVerdict]
