# Fact-Checking Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a Render-hosted React + FastAPI app that uploads PDFs, extracts factual claims, verifies them against live Tavily evidence using OpenRouter, and returns an interactive report plus downloadable JSON.

**Architecture:** The backend is a modular FastAPI service with synchronous fact-checking first and job polling added at the end. The frontend is a Vite React analyst workbench with upload controls, run progress, verdict table, expandable claim details, and JSON export.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, pytest, httpx, pypdf, pdf2image or PyMuPDF for OCR page rendering, OpenRouter Chat Completions API, Tavily Search API, React, TypeScript, Vite, Vitest, Testing Library, Render.

---

## File Structure

Create this structure:

```text
backend/
  app/
    __init__.py
    main.py
    config.py
    models.py
    services/
      __init__.py
      pdf_service.py
      ocr_service.py
      openrouter_client.py
      tavily_client.py
      claim_extractor.py
      claim_grouper.py
      search_service.py
      verifier.py
      orchestrator.py
  tests/
    conftest.py
    test_config.py
    test_pdf_service.py
    test_claim_grouper.py
    test_search_service.py
    test_orchestrator.py
    test_api.py
  requirements.txt
  render.yaml
frontend/
  src/
    App.tsx
    main.tsx
    api.ts
    types.ts
    components/
      UploadPanel.tsx
      ProgressRail.tsx
      VerdictSummary.tsx
      ResultsTable.tsx
      ClaimDetails.tsx
    styles.css
  index.html
  package.json
  tsconfig.json
  vite.config.ts
  render.yaml
README.md
```

Backend responsibilities:

- `config.py`: reads environment variables and exposes limits.
- `models.py`: shared Pydantic request/response and pipeline models.
- `pdf_service.py`: extracts PDF text and identifies pages needing OCR.
- `ocr_service.py`: renders low-text pages and sends images to OpenRouter vision model.
- `openrouter_client.py`: typed client for OpenRouter chat completions.
- `tavily_client.py`: typed client for Tavily search.
- `claim_extractor.py`: converts PDF text into structured claims.
- `claim_grouper.py`: groups related claims by topic.
- `search_service.py`: generates Tavily queries and normalizes evidence.
- `verifier.py`: creates evidence-grounded verdicts.
- `orchestrator.py`: coordinates the fact-check pipeline.
- `main.py`: FastAPI app, CORS, health, synchronous fact-check endpoint, and later job polling endpoints.

Frontend responsibilities:

- `api.ts`: backend API wrapper.
- `types.ts`: shared TypeScript report types.
- `UploadPanel.tsx`: PDF upload, scan mode, run control.
- `ProgressRail.tsx`: visible processing stages.
- `VerdictSummary.tsx`: count badges.
- `ResultsTable.tsx`: compact analyst table.
- `ClaimDetails.tsx`: expandable evidence and reasoning.
- `App.tsx`: page shell and state orchestration.
- `styles.css`: polished workbench styling.

---

### Task 1: Backend Project Skeleton And Configuration

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `backend/app/models.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/tests/test_config.py`
- Create: `backend/requirements.txt`

- [ ] **Step 1: Create backend dependencies**

Write `backend/requirements.txt`:

```txt
fastapi==0.115.6
uvicorn[standard]==0.34.0
python-multipart==0.0.20
pydantic==2.10.5
pydantic-settings==2.7.1
httpx==0.28.1
pypdf==5.1.0
PyMuPDF==1.25.1
pytest==8.3.4
pytest-asyncio==0.25.2
respx==0.22.0
```

- [ ] **Step 2: Write the configuration test**

Write `backend/tests/test_config.py`:

```python
from app.config import Settings


def test_settings_defaults_are_assignment_safe():
    settings = Settings(
        openrouter_api_key="or-key",
        tavily_api_key="tv-key",
    )

    assert settings.openrouter_model
    assert settings.openrouter_vision_model
    assert settings.max_claims_focused == 12
    assert settings.max_claims_deep == 25
    assert settings.max_ocr_pages == 5
    assert settings.max_pdf_size_mb == 10


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
```

- [ ] **Step 3: Run the test to verify it fails**

Run:

```bash
cd backend
pytest tests/test_config.py -v
```

Expected: FAIL because `app.config` does not exist.

- [ ] **Step 4: Implement settings and app skeleton**

Write `backend/app/config.py`:

```python
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="openai/gpt-4o-mini", alias="OPENROUTER_MODEL")
    openrouter_vision_model: str = Field(default="openai/gpt-4o-mini", alias="OPENROUTER_VISION_MODEL")
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    max_claims_focused: int = Field(default=12, alias="MAX_CLAIMS_FOCUSED")
    max_claims_deep: int = Field(default=25, alias="MAX_CLAIMS_DEEP")
    max_ocr_pages: int = Field(default=5, alias="MAX_OCR_PAGES")
    max_pdf_size_mb: int = Field(default=10, alias="MAX_PDF_SIZE_MB")
    tavily_search_depth: str = Field(default="basic", alias="TAVILY_SEARCH_DEPTH")
    frontend_origin: str = Field(default="http://localhost:5173", alias="FRONTEND_ORIGIN")

    @property
    def max_pdf_size_bytes(self) -> int:
        return self.max_pdf_size_mb * 1024 * 1024

    def claim_limit_for_mode(self, mode: str) -> int:
        return self.max_claims_deep if mode == "deep" else self.max_claims_focused

    @property
    def has_required_keys(self) -> bool:
        return bool(self.openrouter_api_key and self.tavily_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Write `backend/app/models.py`:

```python
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
```

Write `backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

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
```

Create empty package markers:

```python
# backend/app/__init__.py
```

```python
# backend/app/services/__init__.py
```

- [ ] **Step 5: Run the config test**

Run:

```bash
cd backend
pytest tests/test_config.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat: scaffold backend configuration"
```

---

### Task 2: PDF Text Extraction With OCR Page Detection

**Files:**
- Create: `backend/app/services/pdf_service.py`
- Create: `backend/tests/test_pdf_service.py`

- [ ] **Step 1: Write PDF service tests**

Write `backend/tests/test_pdf_service.py`:

```python
import io

import fitz

from app.services.pdf_service import extract_pdf_pages, find_pages_needing_ocr


def make_pdf(page_texts: list[str]) -> bytes:
    doc = fitz.open()
    for text in page_texts:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_extract_pdf_pages_keeps_page_numbers():
    pdf_bytes = make_pdf(["Revenue grew 15% in 2024.", "The company has 2 million users."])

    pages = extract_pdf_pages(io.BytesIO(pdf_bytes))

    assert [page.page_number for page in pages] == [1, 2]
    assert "Revenue grew 15%" in pages[0].text
    assert pages[0].source == "pdf"


def test_find_pages_needing_ocr_uses_minimum_text_threshold():
    pdf_bytes = make_pdf(["", "A real text page with enough words to skip OCR."])
    pages = extract_pdf_pages(io.BytesIO(pdf_bytes))

    ocr_pages = find_pages_needing_ocr(pages, min_chars=20)

    assert ocr_pages == [1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
pytest tests/test_pdf_service.py -v
```

Expected: FAIL because `pdf_service.py` does not exist.

- [ ] **Step 3: Implement PDF service**

Write `backend/app/services/pdf_service.py`:

```python
from typing import BinaryIO

from pypdf import PdfReader

from app.models import PageText


def extract_pdf_pages(file_obj: BinaryIO) -> list[PageText]:
    reader = PdfReader(file_obj)
    pages: list[PageText] = []

    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(PageText(page_number=index, text=text.strip(), source="pdf"))

    return pages


def find_pages_needing_ocr(pages: list[PageText], min_chars: int = 40) -> list[int]:
    return [page.page_number for page in pages if len(page.text.strip()) < min_chars]
```

- [ ] **Step 4: Run PDF service tests**

Run:

```bash
cd backend
pytest tests/test_pdf_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/pdf_service.py backend/tests/test_pdf_service.py
git commit -m "feat: extract PDF text by page"
```

---

### Task 3: Claim Grouping And Report Summary

**Files:**
- Create: `backend/app/services/claim_grouper.py`
- Create: `backend/tests/test_claim_grouper.py`

- [ ] **Step 1: Write grouping tests**

Write `backend/tests/test_claim_grouper.py`:

```python
from app.models import ExtractedClaim
from app.services.claim_grouper import build_report_summary, group_claims


def claim(id_: str, topic: str, text: str = "Claim text") -> ExtractedClaim:
    return ExtractedClaim(
        id=id_,
        text=text,
        page_number=1,
        claim_type="statistic",
        topic=topic,
        importance="medium",
    )


def test_group_claims_normalizes_topic_names():
    groups = group_claims([
        claim("c1", "Global AI Market"),
        claim("c2", "global ai market "),
        claim("c3", "Customer Count"),
    ])

    assert list(groups.keys()) == ["global ai market", "customer count"]
    assert [item.id for item in groups["global ai market"]] == ["c1", "c2"]


def test_build_report_summary_counts_verdicts():
    summary = build_report_summary(["Verified", "Verified", "Inaccurate", "False / Unsupported"])

    assert summary == {
        "total": 4,
        "verified": 2,
        "inaccurate": 1,
        "false_or_unsupported": 1,
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
pytest tests/test_claim_grouper.py -v
```

Expected: FAIL because `claim_grouper.py` does not exist.

- [ ] **Step 3: Implement grouping**

Write `backend/app/services/claim_grouper.py`:

```python
from collections import OrderedDict

from app.models import ExtractedClaim, VerdictLabel


def normalize_topic(topic: str) -> str:
    return " ".join(topic.lower().strip().split()) or "general"


def group_claims(claims: list[ExtractedClaim]) -> dict[str, list[ExtractedClaim]]:
    groups: OrderedDict[str, list[ExtractedClaim]] = OrderedDict()
    for claim in claims:
        key = normalize_topic(claim.topic)
        groups.setdefault(key, []).append(claim)
    return dict(groups)


def build_report_summary(verdicts: list[VerdictLabel]) -> dict[str, int]:
    return {
        "total": len(verdicts),
        "verified": sum(1 for verdict in verdicts if verdict == "Verified"),
        "inaccurate": sum(1 for verdict in verdicts if verdict == "Inaccurate"),
        "false_or_unsupported": sum(1 for verdict in verdicts if verdict == "False / Unsupported"),
    }
```

- [ ] **Step 4: Run grouping tests**

Run:

```bash
cd backend
pytest tests/test_claim_grouper.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/claim_grouper.py backend/tests/test_claim_grouper.py
git commit -m "feat: group claims and summarize verdicts"
```

---

### Task 4: Tavily Search Normalization

**Files:**
- Create: `backend/app/services/tavily_client.py`
- Create: `backend/app/services/search_service.py`
- Create: `backend/tests/test_search_service.py`

- [ ] **Step 1: Write search normalization tests**

Write `backend/tests/test_search_service.py`:

```python
import pytest

from app.models import ExtractedClaim
from app.services.search_service import build_search_queries, normalize_tavily_results


def test_build_search_queries_uses_topic_and_claim_text():
    claim = ExtractedClaim(
        id="c1",
        text="The global AI market reached $500 billion in 2024.",
        page_number=2,
        claim_type="financial figure",
        topic="Global AI market",
        importance="high",
    )

    queries = build_search_queries("global ai market", [claim])

    assert queries[0] == "global ai market latest official data"
    assert "global AI market reached $500 billion" in queries[1]


def test_normalize_tavily_results_keeps_url_title_snippet_and_query():
    raw = {
        "results": [
            {
                "title": "Market report",
                "url": "https://example.com/report",
                "content": "The latest market estimate is lower.",
                "published_date": "2026-01-02",
            }
        ]
    }

    evidence = normalize_tavily_results(raw, query="market query")

    assert evidence[0].title == "Market report"
    assert str(evidence[0].url) == "https://example.com/report"
    assert evidence[0].snippet == "The latest market estimate is lower."
    assert evidence[0].published_date == "2026-01-02"
    assert evidence[0].query == "market query"


def test_normalize_tavily_results_skips_items_without_url():
    raw = {"results": [{"title": "No URL", "content": "Missing URL"}]}

    assert normalize_tavily_results(raw, query="query") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
pytest tests/test_search_service.py -v
```

Expected: FAIL because search modules do not exist.

- [ ] **Step 3: Implement Tavily client and search service**

Write `backend/app/services/tavily_client.py`:

```python
import httpx


class TavilyClient:
    def __init__(self, api_key: str, search_depth: str = "basic") -> None:
        self.api_key = api_key
        self.search_depth = search_depth

    async def search(self, query: str, max_results: int = 5) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": self.search_depth,
                    "max_results": max_results,
                    "include_answer": False,
                    "include_raw_content": False,
                },
            )
            response.raise_for_status()
            return response.json()
```

Write `backend/app/services/search_service.py`:

```python
from app.models import EvidenceSource, ExtractedClaim
from app.services.tavily_client import TavilyClient


def build_search_queries(topic: str, claims: list[ExtractedClaim]) -> list[str]:
    queries = [f"{topic} latest official data"]
    for claim in claims[:3]:
        queries.append(f"{claim.text} source")
    return queries


def normalize_tavily_results(raw: dict, query: str) -> list[EvidenceSource]:
    evidence: list[EvidenceSource] = []
    for item in raw.get("results", []):
        url = item.get("url")
        if not url:
            continue
        snippet = item.get("content") or item.get("snippet") or ""
        evidence.append(
            EvidenceSource(
                title=item.get("title") or url,
                url=url,
                snippet=snippet,
                published_date=item.get("published_date"),
                query=query,
            )
        )
    return evidence


async def gather_evidence_for_group(
    tavily_client: TavilyClient,
    topic: str,
    claims: list[ExtractedClaim],
    max_results_per_query: int = 3,
) -> list[EvidenceSource]:
    evidence: list[EvidenceSource] = []
    for query in build_search_queries(topic, claims):
        raw = await tavily_client.search(query, max_results=max_results_per_query)
        evidence.extend(normalize_tavily_results(raw, query))
    return evidence
```

- [ ] **Step 4: Run search tests**

Run:

```bash
cd backend
pytest tests/test_search_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/tavily_client.py backend/app/services/search_service.py backend/tests/test_search_service.py
git commit -m "feat: normalize Tavily evidence"
```

---

### Task 5: OpenRouter Client, Claim Extraction, OCR, And Verification

**Files:**
- Create: `backend/app/services/openrouter_client.py`
- Create: `backend/app/services/claim_extractor.py`
- Create: `backend/app/services/ocr_service.py`
- Create: `backend/app/services/verifier.py`
- Create: `backend/tests/test_orchestrator.py`

- [ ] **Step 1: Write orchestration tests using fake AI/search services**

Write `backend/tests/test_orchestrator.py`:

```python
from app.models import ClaimVerdict, EvidenceSource, ExtractedClaim, ScanMode
from app.services.orchestrator import FactCheckOrchestrator


class FakePdfService:
    def extract(self, _file_obj):
        return []


class FakeClaimExtractor:
    async def extract_claims(self, pages, mode, limit):
        return [
            ExtractedClaim(
                id="c1",
                text="The company reached 10 million users in 2024.",
                page_number=1,
                claim_type="count",
                topic="company users",
                importance="high",
            )
        ]


class FakeSearchService:
    async def gather(self, topic, claims):
        return [
            EvidenceSource(
                title="Official update",
                url="https://example.com/users",
                snippet="The company reached 8 million users in 2024.",
                query="company users latest official data",
            )
        ]

    async def follow_up(self, claim):
        return []


class FakeVerifier:
    async def verify(self, claim, evidence):
        return ClaimVerdict(
            claim=claim,
            verdict="Inaccurate",
            corrected_fact="The company reported 8 million users in 2024.",
            confidence="High",
            reasoning="The source gives a lower official count.",
            sources=evidence,
            search_queries=[source.query for source in evidence],
        )


async def test_orchestrator_returns_summary_and_claim_results():
    orchestrator = FactCheckOrchestrator(
        claim_extractor=FakeClaimExtractor(),
        search_service=FakeSearchService(),
        verifier=FakeVerifier(),
        settings_claim_limit=lambda mode: 12,
    )

    report = await orchestrator.run(
        file_name="trap.pdf",
        pages=[],
        mode=ScanMode.focused,
    )

    assert report.summary["total"] == 1
    assert report.summary["inaccurate"] == 1
    assert report.claims[0].corrected_fact == "The company reported 8 million users in 2024."
```

- [ ] **Step 2: Run the orchestration test to verify it fails**

Run:

```bash
cd backend
pytest tests/test_orchestrator.py -v
```

Expected: FAIL because `orchestrator.py` and AI service modules do not exist.

- [ ] **Step 3: Implement OpenRouter client**

Write `backend/app/services/openrouter_client.py`:

```python
import base64
import json
from typing import Any

import httpx


class OpenRouterClient:
    def __init__(self, api_key: str, model: str, vision_model: str) -> None:
        self.api_key = api_key
        self.model = model
        self.vision_model = vision_model

    async def chat_json(self, system: str, user: str, model: str | None = None) -> dict[str, Any]:
        content = await self.chat_text(system=system, user=user, model=model)
        return json.loads(content)

    async def chat_text(self, system: str, user: str, model: str | None = None) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://fact-check-agent.render.com",
                    "X-Title": "Fact-Check Agent",
                },
                json={
                    "model": model or self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            payload = response.json()
            return payload["choices"][0]["message"]["content"]

    async def vision_ocr(self, image_bytes: bytes) -> str:
        data_uri = "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://fact-check-agent.render.com",
                    "X-Title": "Fact-Check Agent",
                },
                json={
                    "model": self.vision_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Extract all readable text from this PDF page image. Return plain text only."},
                                {"type": "image_url", "image_url": {"url": data_uri}},
                            ],
                        }
                    ],
                },
            )
            response.raise_for_status()
            payload = response.json()
            return payload["choices"][0]["message"]["content"].strip()
```

- [ ] **Step 4: Implement claim extraction, OCR, verifier, and orchestrator**

Write `backend/app/services/claim_extractor.py`:

```python
from app.models import ExtractedClaim, PageText, ScanMode
from app.services.openrouter_client import OpenRouterClient


class ClaimExtractor:
    def __init__(self, client: OpenRouterClient) -> None:
        self.client = client

    async def extract_claims(self, pages: list[PageText], mode: ScanMode, limit: int) -> list[ExtractedClaim]:
        source_text = "\n\n".join(f"[Page {page.page_number}]\n{page.text}" for page in pages)
        focus = (
            "Extract only statistics, dates, percentages, counts, money, market sizes, technical figures, rankings, and named measurable claims."
            if mode == ScanMode.focused
            else "Extract concrete factual claims, including qualitative factual assertions when they can be checked."
        )
        payload = await self.client.chat_json(
            system="You extract fact-checkable claims from PDF text. Return valid JSON only.",
            user=(
                f"{focus}\nReturn JSON with a 'claims' array. Each item must include id, text, page_number, "
                f"claim_type, topic, and importance as high, medium, or low. Return at most {limit} claims.\n\n{source_text}"
            ),
        )
        return [ExtractedClaim(**item) for item in payload.get("claims", [])[:limit]]
```

Write `backend/app/services/ocr_service.py`:

```python
import io

import fitz

from app.models import PageText
from app.services.openrouter_client import OpenRouterClient


class OcrService:
    def __init__(self, client: OpenRouterClient, max_pages: int) -> None:
        self.client = client
        self.max_pages = max_pages

    async def extract_pages(self, pdf_bytes: bytes, page_numbers: list[int]) -> list[PageText]:
        results: list[PageText] = []
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            for page_number in page_numbers[: self.max_pages]:
                page = doc.load_page(page_number - 1)
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image_bytes = pixmap.tobytes("png")
                text = await self.client.vision_ocr(image_bytes)
                results.append(PageText(page_number=page_number, text=text, source="ocr"))
        finally:
            doc.close()
        return results
```

Write `backend/app/services/verifier.py`:

```python
from app.models import ClaimVerdict, EvidenceSource, ExtractedClaim
from app.services.openrouter_client import OpenRouterClient


class Verifier:
    def __init__(self, client: OpenRouterClient) -> None:
        self.client = client

    async def verify(self, claim: ExtractedClaim, evidence: list[EvidenceSource]) -> ClaimVerdict:
        evidence_text = "\n".join(
            f"- {source.title} ({source.url}): {source.snippet}" for source in evidence
        )
        payload = await self.client.chat_json(
            system=(
                "You are an evidence-grounded fact checker. Use only the provided evidence. "
                "Return valid JSON only."
            ),
            user=(
                "Classify the claim as exactly one of: Verified, Inaccurate, False / Unsupported.\n"
                "Return JSON fields: verdict, corrected_fact, confidence, reasoning.\n"
                "Confidence must be High, Medium, or Low.\n\n"
                f"Claim: {claim.text}\n\nEvidence:\n{evidence_text}"
            ),
        )
        return ClaimVerdict(
            claim=claim,
            verdict=payload["verdict"],
            corrected_fact=payload.get("corrected_fact"),
            confidence=payload["confidence"],
            reasoning=payload["reasoning"],
            sources=evidence,
            search_queries=sorted({source.query for source in evidence}),
        )
```

Write `backend/app/services/orchestrator.py`:

```python
from collections.abc import Callable

from app.models import FactCheckReport, PageText, ScanMode
from app.services.claim_grouper import build_report_summary, group_claims


class FactCheckOrchestrator:
    def __init__(
        self,
        claim_extractor,
        search_service,
        verifier,
        settings_claim_limit: Callable[[str], int],
    ) -> None:
        self.claim_extractor = claim_extractor
        self.search_service = search_service
        self.verifier = verifier
        self.settings_claim_limit = settings_claim_limit

    async def run(self, file_name: str, pages: list[PageText], mode: ScanMode) -> FactCheckReport:
        limit = self.settings_claim_limit(mode.value)
        claims = await self.claim_extractor.extract_claims(pages, mode, limit)
        grouped = group_claims(claims)
        evidence_by_claim_id = {claim.id: [] for claim in claims}

        for topic, topic_claims in grouped.items():
            evidence = await self.search_service.gather(topic, topic_claims)
            for claim in topic_claims:
                evidence_by_claim_id[claim.id].extend(evidence)

        verdicts = []
        for claim in claims:
            evidence = evidence_by_claim_id[claim.id]
            verdict = await self.verifier.verify(claim, evidence)
            if verdict.confidence == "Low" and claim.importance == "high":
                follow_up = await self.search_service.follow_up(claim)
                if follow_up:
                    verdict = await self.verifier.verify(claim, evidence + follow_up)
            verdicts.append(verdict)

        return FactCheckReport(
            file_name=file_name,
            scan_mode=mode,
            summary=build_report_summary([verdict.verdict for verdict in verdicts]),
            claims=verdicts,
        )
```

- [ ] **Step 5: Run orchestration tests**

Run:

```bash
cd backend
pytest tests/test_orchestrator.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services backend/tests/test_orchestrator.py
git commit -m "feat: add AI fact-check orchestration"
```

---

### Task 6: FastAPI Upload Endpoint

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api.py`

- [ ] **Step 1: Write API tests**

Write `backend/tests/test_api.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_reports_configuration_shape():
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "configured" in body


def test_fact_check_rejects_non_pdf():
    response = client.post(
        "/api/fact-check",
        data={"scan_mode": "focused"},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Please upload a PDF file."
```

- [ ] **Step 2: Run API tests to verify upload test fails**

Run:

```bash
cd backend
pytest tests/test_api.py -v
```

Expected: FAIL because `/api/fact-check` does not exist.

- [ ] **Step 3: Implement endpoint wiring**

Replace `backend/app/main.py` with:

```python
import io

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models import FactCheckReport, ScanMode
from app.services.claim_extractor import ClaimExtractor
from app.services.ocr_service import OcrService
from app.services.openrouter_client import OpenRouterClient
from app.services.orchestrator import FactCheckOrchestrator
from app.services.pdf_service import extract_pdf_pages, find_pages_needing_ocr
from app.services.search_service import gather_evidence_for_group
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


class LiveSearchService:
    def __init__(self, tavily_client: TavilyClient) -> None:
        self.tavily_client = tavily_client

    async def gather(self, topic, claims):
        return await gather_evidence_for_group(self.tavily_client, topic, claims)

    async def follow_up(self, claim):
        query = f"{claim.text} latest official source correction"
        raw = await self.tavily_client.search(query, max_results=5)
        from app.services.search_service import normalize_tavily_results

        return normalize_tavily_results(raw, query)


def build_orchestrator() -> FactCheckOrchestrator:
    openrouter = OpenRouterClient(
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
        vision_model=settings.openrouter_vision_model,
    )
    tavily = TavilyClient(settings.tavily_api_key, settings.tavily_search_depth)
    return FactCheckOrchestrator(
        claim_extractor=ClaimExtractor(openrouter),
        search_service=LiveSearchService(tavily),
        verifier=Verifier(openrouter),
        settings_claim_limit=settings.claim_limit_for_mode,
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


@app.post("/api/fact-check", response_model=FactCheckReport)
async def fact_check(
    scan_mode: ScanMode = Form(default=ScanMode.focused),
    file: UploadFile = File(...),
) -> FactCheckReport:
    if file.content_type != "application/pdf" and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")
    pdf_bytes = await file.read()
    if len(pdf_bytes) > settings.max_pdf_size_bytes:
        raise HTTPException(status_code=400, detail=f"PDF must be {settings.max_pdf_size_mb} MB or smaller.")
    if not settings.has_required_keys:
        raise HTTPException(status_code=503, detail="OpenRouter and Tavily API keys are not configured.")

    pages = extract_pdf_pages(io.BytesIO(pdf_bytes))
    pages_needing_ocr = find_pages_needing_ocr(pages)
    if pages_needing_ocr:
        openrouter = OpenRouterClient(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
            vision_model=settings.openrouter_vision_model,
        )
        ocr_pages = await OcrService(openrouter, settings.max_ocr_pages).extract_pages(pdf_bytes, pages_needing_ocr)
        by_page = {page.page_number: page for page in pages}
        for ocr_page in ocr_pages:
            if len(by_page[ocr_page.page_number].text.strip()) < len(ocr_page.text.strip()):
                by_page[ocr_page.page_number] = ocr_page
        pages = [by_page[number] for number in sorted(by_page)]

    if not any(page.text.strip() for page in pages):
        raise HTTPException(status_code=422, detail="No extractable text found in this PDF.")

    return await build_orchestrator().run(file.filename, pages, scan_mode)
```

- [ ] **Step 4: Run API tests**

Run:

```bash
cd backend
pytest tests/test_api.py -v
```

Expected: PASS.

- [ ] **Step 5: Run all backend tests**

Run:

```bash
cd backend
pytest -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/test_api.py
git commit -m "feat: expose PDF fact-check endpoint"
```

---

### Task 7: Frontend Skeleton And API Types

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/api.ts`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles.css`

- [ ] **Step 1: Create frontend package**

Write `frontend/package.json`:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "@vitejs/plugin-react": "latest",
    "vite": "latest",
    "typescript": "latest",
    "react": "latest",
    "react-dom": "latest",
    "lucide-react": "latest"
  },
  "devDependencies": {
    "@testing-library/react": "latest",
    "@testing-library/jest-dom": "latest",
    "@types/react": "latest",
    "@types/react-dom": "latest",
    "jsdom": "latest",
    "vitest": "latest"
  }
}
```

- [ ] **Step 2: Create Vite config files**

Write `frontend/index.html`:

```html
<div id="root"></div>
<script type="module" src="/src/main.tsx"></script>
```

Write `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2020"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"],
  "references": []
}
```

Write `frontend/vite.config.ts`:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
```

- [ ] **Step 3: Create shared types and API wrapper**

Write `frontend/src/types.ts`:

```ts
export type ScanMode = "focused" | "deep";
export type VerdictLabel = "Verified" | "Inaccurate" | "False / Unsupported";
export type ConfidenceLabel = "High" | "Medium" | "Low";

export interface ExtractedClaim {
  id: string;
  text: string;
  page_number: number | null;
  claim_type: string;
  topic: string;
  importance: "high" | "medium" | "low";
}

export interface EvidenceSource {
  title: string;
  url: string;
  snippet: string;
  published_date: string | null;
  query: string;
}

export interface ClaimVerdict {
  claim: ExtractedClaim;
  verdict: VerdictLabel;
  corrected_fact: string | null;
  confidence: ConfidenceLabel;
  reasoning: string;
  sources: EvidenceSource[];
  search_queries: string[];
}

export interface FactCheckReport {
  file_name: string;
  scan_mode: ScanMode;
  summary: {
    total: number;
    verified: number;
    inaccurate: number;
    false_or_unsupported: number;
  };
  claims: ClaimVerdict[];
}
```

Write `frontend/src/api.ts`:

```ts
import type { FactCheckReport, ScanMode } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function runFactCheck(file: File, scanMode: ScanMode): Promise<FactCheckReport> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("scan_mode", scanMode);

  const response = await fetch(`${API_BASE}/api/fact-check`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "Fact-check failed." }));
    throw new Error(payload.detail ?? "Fact-check failed.");
  }

  return response.json();
}
```

- [ ] **Step 4: Create initial App and styles**

Write `frontend/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

Write `frontend/src/App.tsx`:

```tsx
import { ShieldCheck } from "lucide-react";

export default function App() {
  return (
    <main className="appShell">
      <header className="topBar">
        <div className="brandMark">
          <ShieldCheck size={20} />
          <span>Fact-Check Agent</span>
        </div>
        <span className="statusPill">Ready</span>
      </header>
      <section className="workspace">
        <aside className="controlPanel">
          <h1>PDF fact-check</h1>
          <p>Upload a document to extract measurable claims and verify them against live sources.</p>
        </aside>
        <section className="resultsPane">
          <div className="emptyState">Upload a PDF to begin.</div>
        </section>
      </section>
    </main>
  );
}
```

Write `frontend/src/styles.css`:

```css
:root {
  color: #172026;
  background: #f4f6f7;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-synthesis: none;
  text-rendering: optimizeLegibility;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
}

button,
input {
  font: inherit;
}

.appShell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.topBar {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  border-bottom: 1px solid #d9e0e3;
  background: #ffffff;
}

.brandMark {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
}

.statusPill {
  border: 1px solid #bdd7ca;
  color: #17623f;
  background: #ecf8f1;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 13px;
}

.workspace {
  flex: 1;
  display: grid;
  grid-template-columns: 340px 1fr;
  min-height: 0;
}

.controlPanel {
  border-right: 1px solid #d9e0e3;
  background: #ffffff;
  padding: 24px;
}

.controlPanel h1 {
  margin: 0 0 8px;
  font-size: 24px;
}

.controlPanel p {
  margin: 0;
  color: #596970;
  line-height: 1.5;
}

.resultsPane {
  padding: 24px;
}

.emptyState {
  border: 1px dashed #b8c4c9;
  min-height: 240px;
  display: grid;
  place-items: center;
  color: #617177;
  background: #ffffff;
  border-radius: 8px;
}
```

- [ ] **Step 5: Install and build**

Run:

```bash
cd frontend
npm install
npm run build
```

Expected: build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat: scaffold analyst workbench frontend"
```

---

### Task 8: Frontend Upload, Progress, Results, And JSON Download

**Files:**
- Create: `frontend/src/components/UploadPanel.tsx`
- Create: `frontend/src/components/ProgressRail.tsx`
- Create: `frontend/src/components/VerdictSummary.tsx`
- Create: `frontend/src/components/ResultsTable.tsx`
- Create: `frontend/src/components/ClaimDetails.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Create upload component**

Write `frontend/src/components/UploadPanel.tsx`:

```tsx
import { FileUp, Play } from "lucide-react";
import type { ScanMode } from "../types";

interface Props {
  file: File | null;
  scanMode: ScanMode;
  isRunning: boolean;
  onFileChange: (file: File | null) => void;
  onScanModeChange: (mode: ScanMode) => void;
  onRun: () => void;
}

export function UploadPanel({ file, scanMode, isRunning, onFileChange, onScanModeChange, onRun }: Props) {
  return (
    <div className="uploadPanel">
      <label className="dropZone">
        <FileUp size={22} />
        <span>{file ? file.name : "Choose a PDF"}</span>
        <input
          type="file"
          accept="application/pdf"
          onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
        />
      </label>
      <div className="segmented">
        <button className={scanMode === "focused" ? "active" : ""} onClick={() => onScanModeChange("focused")}>
          Focused
        </button>
        <button className={scanMode === "deep" ? "active" : ""} onClick={() => onScanModeChange("deep")}>
          Deep Scan
        </button>
      </div>
      <button className="runButton" disabled={!file || isRunning} onClick={onRun}>
        <Play size={17} />
        {isRunning ? "Checking..." : "Run fact-check"}
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Create progress and summary components**

Write `frontend/src/components/ProgressRail.tsx`:

```tsx
const stages = ["Extract text", "Read scanned pages", "Extract claims", "Search evidence", "Finalize report"];

export function ProgressRail({ active }: { active: boolean }) {
  return (
    <div className="progressRail">
      {stages.map((stage, index) => (
        <div className={active ? "stage active" : "stage"} key={stage}>
          <span>{index + 1}</span>
          {stage}
        </div>
      ))}
    </div>
  );
}
```

Write `frontend/src/components/VerdictSummary.tsx`:

```tsx
import type { FactCheckReport } from "../types";

export function VerdictSummary({ report }: { report: FactCheckReport }) {
  return (
    <div className="summaryGrid">
      <div><strong>{report.summary.total}</strong><span>Total</span></div>
      <div><strong>{report.summary.verified}</strong><span>Verified</span></div>
      <div><strong>{report.summary.inaccurate}</strong><span>Inaccurate</span></div>
      <div><strong>{report.summary.false_or_unsupported}</strong><span>Unsupported</span></div>
    </div>
  );
}
```

- [ ] **Step 3: Create result table and details**

Write `frontend/src/components/ClaimDetails.tsx`:

```tsx
import type { ClaimVerdict } from "../types";

export function ClaimDetails({ item }: { item: ClaimVerdict }) {
  return (
    <div className="claimDetails">
      <p><strong>Reasoning:</strong> {item.reasoning}</p>
      {item.corrected_fact && <p><strong>Corrected fact:</strong> {item.corrected_fact}</p>}
      <div className="sources">
        {item.sources.map((source) => (
          <a href={source.url} target="_blank" rel="noreferrer" key={`${source.url}-${source.query}`}>
            <strong>{source.title}</strong>
            <span>{source.snippet}</span>
          </a>
        ))}
      </div>
    </div>
  );
}
```

Write `frontend/src/components/ResultsTable.tsx`:

```tsx
import { useState } from "react";
import type { ClaimVerdict, VerdictLabel } from "../types";
import { ClaimDetails } from "./ClaimDetails";

const verdictClass: Record<VerdictLabel, string> = {
  Verified: "verified",
  Inaccurate: "inaccurate",
  "False / Unsupported": "unsupported",
};

export function ResultsTable({ claims }: { claims: ClaimVerdict[] }) {
  const [openId, setOpenId] = useState<string | null>(null);

  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            <th>Verdict</th>
            <th>Claim</th>
            <th>Correction</th>
            <th>Confidence</th>
            <th>Sources</th>
          </tr>
        </thead>
        <tbody>
          {claims.map((item) => (
            <>
              <tr key={item.claim.id} onClick={() => setOpenId(openId === item.claim.id ? null : item.claim.id)}>
                <td><span className={`badge ${verdictClass[item.verdict]}`}>{item.verdict}</span></td>
                <td>{item.claim.text}</td>
                <td>{item.corrected_fact ?? "No correction"}</td>
                <td>{item.confidence}</td>
                <td>{item.sources.length}</td>
              </tr>
              {openId === item.claim.id && (
                <tr key={`${item.claim.id}-details`}>
                  <td colSpan={5}><ClaimDetails item={item} /></td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 4: Wire App state**

Replace `frontend/src/App.tsx` with:

```tsx
import { Download, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { runFactCheck } from "./api";
import { ProgressRail } from "./components/ProgressRail";
import { ResultsTable } from "./components/ResultsTable";
import { UploadPanel } from "./components/UploadPanel";
import { VerdictSummary } from "./components/VerdictSummary";
import type { FactCheckReport, ScanMode } from "./types";

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [scanMode, setScanMode] = useState<ScanMode>("focused");
  const [report, setReport] = useState<FactCheckReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  const downloadUrl = useMemo(() => {
    if (!report) return null;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    return URL.createObjectURL(blob);
  }, [report]);

  async function handleRun() {
    if (!file) return;
    setIsRunning(true);
    setError(null);
    setReport(null);
    try {
      setReport(await runFactCheck(file, scanMode));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fact-check failed.");
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <main className="appShell">
      <header className="topBar">
        <div className="brandMark">
          <ShieldCheck size={20} />
          <span>Fact-Check Agent</span>
        </div>
        <span className="statusPill">{isRunning ? "Running" : "Ready"}</span>
      </header>
      <section className="workspace">
        <aside className="controlPanel">
          <h1>PDF fact-check</h1>
          <p>Extract measurable claims and verify them against live sources.</p>
          <UploadPanel
            file={file}
            scanMode={scanMode}
            isRunning={isRunning}
            onFileChange={setFile}
            onScanModeChange={setScanMode}
            onRun={handleRun}
          />
          <ProgressRail active={isRunning} />
        </aside>
        <section className="resultsPane">
          {error && <div className="errorBox">{error}</div>}
          {!report && !error && <div className="emptyState">Upload a PDF to begin.</div>}
          {report && (
            <>
              <div className="reportHeader">
                <div>
                  <h2>{report.file_name}</h2>
                  <p>{report.scan_mode === "focused" ? "Focused scan" : "Deep scan"}</p>
                </div>
                {downloadUrl && (
                  <a className="downloadButton" href={downloadUrl} download="fact-check-report.json">
                    <Download size={17} />
                    JSON
                  </a>
                )}
              </div>
              <VerdictSummary report={report} />
              <ResultsTable claims={report.claims} />
            </>
          )}
        </section>
      </section>
    </main>
  );
}
```

- [ ] **Step 5: Extend styles for the workbench**

Append to `frontend/src/styles.css`:

```css
.uploadPanel {
  display: grid;
  gap: 14px;
  margin: 24px 0;
}

.dropZone {
  border: 1px dashed #9cafb7;
  border-radius: 8px;
  padding: 18px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  color: #314047;
  background: #f8fafb;
}

.dropZone input {
  display: none;
}

.segmented {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border: 1px solid #cfd8dc;
  border-radius: 8px;
  overflow: hidden;
}

.segmented button {
  border: 0;
  padding: 10px;
  background: #ffffff;
  cursor: pointer;
}

.segmented button.active {
  background: #123d4a;
  color: #ffffff;
}

.runButton,
.downloadButton {
  border: 0;
  border-radius: 8px;
  background: #123d4a;
  color: #ffffff;
  padding: 11px 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  text-decoration: none;
  cursor: pointer;
}

.runButton:disabled {
  background: #9aa9af;
  cursor: not-allowed;
}

.progressRail {
  display: grid;
  gap: 8px;
}

.stage {
  color: #66777e;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.stage span {
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: #e6ecef;
  color: #425158;
  font-size: 12px;
}

.stage.active span {
  background: #123d4a;
  color: #ffffff;
}

.errorBox {
  border: 1px solid #e0b4a8;
  background: #fff3ef;
  color: #8a2f18;
  border-radius: 8px;
  padding: 14px;
  margin-bottom: 16px;
}

.reportHeader {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.reportHeader h2 {
  margin: 0;
  font-size: 22px;
}

.reportHeader p {
  margin: 4px 0 0;
  color: #617177;
}

.summaryGrid {
  display: grid;
  grid-template-columns: repeat(4, minmax(110px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.summaryGrid div {
  border: 1px solid #d9e0e3;
  background: #ffffff;
  border-radius: 8px;
  padding: 14px;
}

.summaryGrid strong,
.summaryGrid span {
  display: block;
}

.summaryGrid strong {
  font-size: 24px;
}

.summaryGrid span {
  color: #617177;
  font-size: 13px;
}

.tableWrap {
  border: 1px solid #d9e0e3;
  border-radius: 8px;
  overflow: hidden;
  background: #ffffff;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  text-align: left;
  vertical-align: top;
  padding: 12px;
  border-bottom: 1px solid #edf1f2;
  font-size: 14px;
}

th {
  background: #f8fafb;
  color: #45545b;
  font-size: 12px;
  text-transform: uppercase;
}

tbody tr {
  cursor: pointer;
}

.badge {
  display: inline-flex;
  border-radius: 999px;
  padding: 4px 8px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.badge.verified {
  color: #17623f;
  background: #ecf8f1;
}

.badge.inaccurate {
  color: #8a5a00;
  background: #fff4d6;
}

.badge.unsupported {
  color: #8a2f18;
  background: #fff3ef;
}

.claimDetails {
  background: #f8fafb;
  padding: 6px 0;
}

.sources {
  display: grid;
  gap: 8px;
}

.sources a {
  display: grid;
  gap: 4px;
  color: #123d4a;
  text-decoration: none;
  border-left: 3px solid #b8cbd1;
  padding-left: 10px;
}

.sources span {
  color: #53636a;
}

@media (max-width: 860px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .controlPanel {
    border-right: 0;
    border-bottom: 1px solid #d9e0e3;
  }

  .summaryGrid {
    grid-template-columns: repeat(2, 1fr);
  }
}
```

- [ ] **Step 6: Build frontend**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "feat: build fact-check report workbench"
```

---

### Task 9: Job Polling Upgrade

**Files:**
- Modify: `backend/app/main.py`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add in-memory job models in backend**

In `backend/app/main.py`, add after `build_orchestrator`:

```python
import asyncio
from uuid import uuid4

jobs: dict[str, dict[str, object]] = {}
```

- [ ] **Step 2: Add backend job endpoints**

In `backend/app/main.py`, add:

```python
async def run_job(job_id: str, file_name: str, pdf_bytes: bytes, scan_mode: ScanMode) -> None:
    try:
        jobs[job_id] = {"status": "running", "progress": "Extracting PDF text", "report": None, "error": None}
        pages = extract_pdf_pages(io.BytesIO(pdf_bytes))
        pages_needing_ocr = find_pages_needing_ocr(pages)
        if pages_needing_ocr:
            jobs[job_id]["progress"] = "Reading scanned pages"
            openrouter = OpenRouterClient(
                api_key=settings.openrouter_api_key,
                model=settings.openrouter_model,
                vision_model=settings.openrouter_vision_model,
            )
            ocr_pages = await OcrService(openrouter, settings.max_ocr_pages).extract_pages(pdf_bytes, pages_needing_ocr)
            by_page = {page.page_number: page for page in pages}
            for ocr_page in ocr_pages:
                if len(by_page[ocr_page.page_number].text.strip()) < len(ocr_page.text.strip()):
                    by_page[ocr_page.page_number] = ocr_page
            pages = [by_page[number] for number in sorted(by_page)]
        if not any(page.text.strip() for page in pages):
            raise ValueError("No extractable text found in this PDF.")
        jobs[job_id]["progress"] = "Extracting claims and checking evidence"
        report = await build_orchestrator().run(file_name, pages, scan_mode)
        jobs[job_id] = {"status": "complete", "progress": "Complete", "report": report.model_dump(mode="json"), "error": None}
    except Exception as exc:
        jobs[job_id] = {"status": "failed", "progress": "Failed", "report": None, "error": str(exc)}


@app.post("/api/jobs")
async def create_job(
    scan_mode: ScanMode = Form(default=ScanMode.focused),
    file: UploadFile = File(...),
) -> dict[str, str]:
    if file.content_type != "application/pdf" and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")
    pdf_bytes = await file.read()
    if len(pdf_bytes) > settings.max_pdf_size_bytes:
        raise HTTPException(status_code=400, detail=f"PDF must be {settings.max_pdf_size_mb} MB or smaller.")
    if not settings.has_required_keys:
        raise HTTPException(status_code=503, detail="OpenRouter and Tavily API keys are not configured.")
    job_id = str(uuid4())
    jobs[job_id] = {"status": "queued", "progress": "Queued", "report": None, "error": None}
    asyncio.create_task(run_job(job_id, file.filename, pdf_bytes, scan_mode))
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, object]:
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")
    return jobs[job_id]
```

- [ ] **Step 3: Add frontend job API**

Append to `frontend/src/api.ts`:

```ts
export async function createFactCheckJob(file: File, scanMode: ScanMode): Promise<string> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("scan_mode", scanMode);

  const response = await fetch(`${API_BASE}/api/jobs`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "Could not start job." }));
    throw new Error(payload.detail ?? "Could not start job.");
  }

  const payload = await response.json();
  return payload.job_id;
}

export async function getFactCheckJob(jobId: string): Promise<{
  status: "queued" | "running" | "complete" | "failed";
  progress: string;
  report: FactCheckReport | null;
  error: string | null;
}> {
  const response = await fetch(`${API_BASE}/api/jobs/${jobId}`);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "Could not read job." }));
    throw new Error(payload.detail ?? "Could not read job.");
  }
  return response.json();
}
```

- [ ] **Step 4: Update frontend to poll jobs**

In `frontend/src/App.tsx`, replace the import:

```tsx
import { createFactCheckJob, getFactCheckJob } from "./api";
```

Replace `handleRun` with:

```tsx
async function handleRun() {
  if (!file) return;
  setIsRunning(true);
  setError(null);
  setReport(null);
  try {
    const jobId = await createFactCheckJob(file, scanMode);
    for (let attempt = 0; attempt < 180; attempt += 1) {
      const job = await getFactCheckJob(jobId);
      if (job.status === "complete" && job.report) {
        setReport(job.report);
        return;
      }
      if (job.status === "failed") {
        throw new Error(job.error ?? "Fact-check job failed.");
      }
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
    }
    throw new Error("Fact-check job timed out.");
  } catch (err) {
    setError(err instanceof Error ? err.message : "Fact-check failed.");
  } finally {
    setIsRunning(false);
  }
}
```

- [ ] **Step 5: Run backend and frontend checks**

Run:

```bash
cd backend
pytest -v
```

Expected: PASS.

Run:

```bash
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py frontend/src/api.ts frontend/src/App.tsx
git commit -m "feat: add fact-check job polling"
```

---

### Task 10: Render Deployment Configuration And README

**Files:**
- Create: `backend/render.yaml`
- Create: `frontend/render.yaml`
- Create: `README.md`

- [ ] **Step 1: Add backend Render config**

Write `backend/render.yaml`:

```yaml
services:
  - type: web
    name: fact-check-agent-api
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: OPENROUTER_API_KEY
        sync: false
      - key: OPENROUTER_MODEL
        value: openai/gpt-4o-mini
      - key: OPENROUTER_VISION_MODEL
        value: openai/gpt-4o-mini
      - key: TAVILY_API_KEY
        sync: false
      - key: MAX_CLAIMS_FOCUSED
        value: "12"
      - key: MAX_CLAIMS_DEEP
        value: "25"
      - key: MAX_OCR_PAGES
        value: "5"
      - key: MAX_PDF_SIZE_MB
        value: "10"
```

- [ ] **Step 2: Add frontend Render config**

Write `frontend/render.yaml`:

```yaml
services:
  - type: web
    name: fact-check-agent-web
    env: static
    buildCommand: npm install && npm run build
    staticPublishPath: dist
    envVars:
      - key: VITE_API_BASE_URL
        sync: false
```

- [ ] **Step 3: Write README**

Write `README.md`:

```markdown
# Fact-Check Agent

Fact-Check Agent is a Render-deployed web app for uploading PDFs, extracting factual claims, checking them against live Tavily search evidence, and producing an evidence-grounded report with OpenRouter.

## Features

- PDF upload
- Focused and Deep Scan modes
- PDF text extraction with OpenRouter vision OCR fallback for scanned pages
- Tavily live web evidence
- OpenRouter claim extraction and verdict synthesis
- Verdicts: Verified, Inaccurate, False / Unsupported
- Interactive results table
- Source URLs and reasoning per claim
- Downloadable JSON report

## Local Setup

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set OPENROUTER_API_KEY=your_openrouter_key
set TAVILY_API_KEY=your_tavily_key
uvicorn app.main:app --reload
```

Backend runs on `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
set VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

Frontend runs on `http://localhost:5173`.

## Render Deployment

Deploy the backend as a Python web service:

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Set `OPENROUTER_API_KEY`
- Set `TAVILY_API_KEY`
- Set `FRONTEND_ORIGIN` to the deployed frontend URL

Deploy the frontend as a static site:

- Build command: `npm install && npm run build`
- Publish directory: `dist`
- Set `VITE_API_BASE_URL` to the deployed backend URL

## Live URL

Add deployed frontend URL here after Render deployment.
```

- [ ] **Step 4: Run final checks**

Run:

```bash
cd backend
pytest -v
```

Expected: PASS.

Run:

```bash
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md backend/render.yaml frontend/render.yaml
git commit -m "docs: add Render deployment guide"
```

---

## Final Verification

- [ ] Run backend tests:

```bash
cd backend
pytest -v
```

- [ ] Build frontend:

```bash
cd frontend
npm run build
```

- [ ] Start backend locally:

```bash
cd backend
uvicorn app.main:app --reload
```

- [ ] Start frontend locally:

```bash
cd frontend
npm run dev
```

- [ ] Upload a text-based PDF and confirm the report renders.
- [ ] Upload a scanned PDF and confirm OCR fallback is attempted.
- [ ] Download JSON and confirm it contains verdicts, corrected facts, sources, and search queries.
- [ ] Deploy backend and frontend on Render.
- [ ] Add live frontend URL to `README.md`.
- [ ] Commit final README URL update.

---

## Self-Review

Spec coverage:

- Render deployment: Task 10.
- React + FastAPI structure: Tasks 1, 6, 7, 8.
- OpenRouter and Tavily: Tasks 4, 5, 6.
- OCR fallback through OpenRouter vision model: Tasks 5 and 6.
- Focused and Deep Scan modes: Tasks 1, 5, 6, 8.
- Hybrid batched plus adaptive search: Tasks 4 and 5.
- Interactive report and JSON download: Task 8.
- Job polling pushed to the end: Task 9.
- Tests and mocked services: Tasks 1 through 6, plus final verification.

Placeholder scan:

- No placeholder markers or unspecified implementation steps remain.
- Every code-writing step includes concrete file content or exact code snippets.

Type consistency:

- Backend Pydantic fields use snake_case.
- Frontend TypeScript fields match backend JSON names.
- Verdict labels match exactly: `Verified`, `Inaccurate`, `False / Unsupported`.
