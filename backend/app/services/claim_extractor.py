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
        claims = [ExtractedClaim.model_validate(item) for item in raw_claims]
        return claims[:limit]
