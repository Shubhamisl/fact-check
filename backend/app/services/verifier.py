from app.models import ClaimVerdict, EvidenceSource, ExtractedClaim
from app.services.openrouter_client import OpenRouterClient


class Verifier:
    def __init__(self, client: OpenRouterClient | None = None) -> None:
        self.client = client or OpenRouterClient()

    async def verify(
        self,
        claim: ExtractedClaim,
        evidence: list[EvidenceSource],
    ) -> ClaimVerdict:
        evidence_text = "\n\n".join(
            (
                f"Source {index}: {source.title}\n"
                f"URL: {source.url}\n"
                f"Query: {source.query}\n"
                f"Published: {source.published_date or 'unknown'}\n"
                f"Snippet: {source.snippet}"
            )
            for index, source in enumerate(evidence, start=1)
        )
        system = (
            "You are an evidence-grounded fact checker. Judge the claim only using "
            "the provided evidence. Return JSON with verdict ('Verified', "
            "'Inaccurate', or 'False / Unsupported'), corrected_fact, confidence "
            "('High', 'Medium', or 'Low'), and reasoning."
        )
        user = (
            f"Claim: {claim.text}\n"
            f"Topic: {claim.topic}\n"
            f"Evidence:\n{evidence_text or 'No evidence supplied.'}"
        )

        data = await self.client.chat_json(system=system, user=user)
        search_queries = sorted({source.query for source in evidence if source.query})
        return ClaimVerdict(
            claim=claim,
            verdict=data["verdict"],
            corrected_fact=data.get("corrected_fact"),
            confidence=data["confidence"],
            reasoning=data["reasoning"],
            sources=evidence,
            search_queries=search_queries,
        )
