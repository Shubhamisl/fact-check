import re

from pydantic import ValidationError

from app.models import ExtractedClaim, PageText, ScanMode
from app.services.openrouter_client import OpenRouterClient


FOCUSED_PROMPT = (
    "Extract only specific, measurable factual claims that can be checked against "
    "external evidence. Prefer numbers, dates, rankings, legal/regulatory claims, "
    "product capabilities, market facts, and named entity assertions."
)

DEEP_PROMPT = (
    "Extract a comprehensive set of checkable factual claims. Include measurable "
    "claims, causal claims, comparisons, temporal assertions, and concrete claims "
    "about named entities. Skip opinions, vague marketing language, and advice."
)

CLAIM_SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")
REPORTED_CLAIM_PATTERN = re.compile(
    r"^(?:one draft|another paragraph|the document|the report|this brief|the copy|"
    r"the paragraph|the deck|the page)\s+(?:says|states|claims|reports)\s+that\s+(.+)$",
    re.IGNORECASE,
)
TRAILING_CONTEXT_PATTERN = re.compile(
    r",\s+(?:a figure|which|an important|a timeline|a claim|a number)\b.*$",
    re.IGNORECASE,
)
SIGNAL_PATTERN = re.compile(
    r"(\b\d+(?:,\d{3})*(?:\.\d+)?\s?(?:%|percent|million|billion|trillion|"
    r"meters?|people|users?|employees?|countries?|years?|GB|TB|MB|AI|USD|"
    r"dollars?)\b|\$\s?\d+|\b(?:19|20)\d{2}\b|\b(?:January|February|March|"
    r"April|May|June|July|August|September|October|November|December)\b)",
    re.IGNORECASE,
)


def normalize_claim_text(text: str) -> str:
    normalized = " ".join(text.strip().split())
    reported_match = REPORTED_CLAIM_PATTERN.match(normalized)
    if reported_match:
        normalized = reported_match.group(1).strip()
    normalized = TRAILING_CONTEXT_PATTERN.sub("", normalized).strip()
    return normalized


def classify_claim_type(text: str) -> str:
    lowered = text.lower()
    if "$" in text or any(word in lowered for word in ("market", "revenue", "valuation")):
        return "financial figure"
    if "%" in text or "percent" in lowered:
        return "percentage"
    if any(month.lower() in lowered for month in (
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    )):
        return "date"
    if re.search(r"\b(?:19|20)\d{2}\b", text):
        return "date"
    return "statistic"


def infer_topic(text: str) -> str:
    words = re.findall(r"[A-Z][A-Za-z0-9-]+", text)
    topic = " ".join(words[:4]).strip()
    return topic or "general facts"


def fallback_extract_claims(pages: list[PageText], limit: int) -> list[ExtractedClaim]:
    claims: list[ExtractedClaim] = []
    seen: set[str] = set()

    for page in pages:
        sentences = CLAIM_SENTENCE_PATTERN.split(page.text.replace("\n", " "))
        for sentence in sentences:
            text = normalize_claim_text(sentence)
            if len(text) < 20 or text in seen or not SIGNAL_PATTERN.search(text):
                continue
            seen.add(text)
            claims.append(
                ExtractedClaim(
                    id=f"claim-{len(claims) + 1}",
                    text=text,
                    page_number=page.page_number,
                    claim_type=classify_claim_type(text),
                    topic=infer_topic(text),
                    importance="high",
                )
            )
            if len(claims) >= limit:
                return claims

    return claims


class ClaimExtractor:
    def __init__(self, client: OpenRouterClient | None = None) -> None:
        self.client = client or OpenRouterClient()

    async def extract_claims(
        self,
        pages: list[PageText],
        mode: ScanMode,
        limit: int,
    ) -> list[ExtractedClaim]:
        page_text = "\n\n".join(
            f"[Page {page.page_number}]\n{page.text.strip()}" for page in pages
        )
        extraction_prompt = DEEP_PROMPT if mode == ScanMode.deep else FOCUSED_PROMPT
        system = (
            "You are a precise fact-checking claim extraction engine. Return JSON "
            "with a top-level 'claims' array. Each claim must include id, text, "
            "page_number, claim_type, topic, and importance ('high', 'medium', or 'low')."
        )
        user = (
            f"{extraction_prompt}\n\n"
            f"Return at most {limit} claims. Use stable ids like claim-1.\n\n"
            f"Document text:\n{page_text}"
        )

        data = await self.client.chat_json(system=system, user=user)
        raw_claims = data if isinstance(data, list) else data.get("claims", [])
        claims: list[ExtractedClaim] = []
        for item in raw_claims:
            try:
                claim = ExtractedClaim.model_validate(item)
            except ValidationError:
                continue
            normalized_text = normalize_claim_text(claim.text)
            claims.append(claim.model_copy(update={"text": normalized_text}))
        if claims:
            return claims[:limit]

        return fallback_extract_claims(pages, limit)
