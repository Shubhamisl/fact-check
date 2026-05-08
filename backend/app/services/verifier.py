from app.models import ClaimVerdict, EvidenceSource, ExtractedClaim
from app.services.openrouter_client import OpenRouterClient


VALID_VERDICTS = {"Verified", "Inaccurate", "False / Unsupported"}
VALID_CONFIDENCE = {"High", "Medium", "Low"}
EMPTY_CORRECTIONS = {"", "none", "null", "n/a", "not applicable", "no correction needed"}


def normalize_verdict(value: object) -> str:
    verdict = str(value or "").strip()
    if verdict in VALID_VERDICTS:
        return verdict
    lowered = verdict.lower()
    if "unsupported" in lowered or "false" in lowered or "contradict" in lowered:
        return "False / Unsupported"
    if "accurate" in lowered or "outdated" in lowered:
        return "Inaccurate"
    if "verified" in lowered or "true" in lowered or "supported" in lowered:
        return "Verified"
    return "False / Unsupported"


def normalize_confidence(value: object) -> str:
    confidence = str(value or "").strip().title()
    if confidence in VALID_CONFIDENCE:
        return confidence
    return "Low"


def normalize_corrected_fact(value: object) -> str | None:
    if value is None:
        return None

    corrected_fact = str(value).strip()
    if corrected_fact.lower() in EMPTY_CORRECTIONS:
        return None
    return corrected_fact


def normalize_claim_verdict(raw_verdict: object, corrected_fact: str | None) -> str:
    verdict = normalize_verdict(raw_verdict)
    if verdict == "Verified" and corrected_fact:
        return "Inaccurate"
    return verdict


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
            "('High', 'Medium', or 'Low'), and reasoning. Use Verified only when "
            "the claim matches the evidence as written. If you provide a corrected "
            "fact, the verdict must be Inaccurate."
        )
        user = (
            f"Claim: {claim.text}\n"
            f"Topic: {claim.topic}\n"
            f"Evidence:\n{evidence_text or 'No evidence supplied.'}"
        )

        data = await self.client.chat_json(system=system, user=user)
        search_queries = sorted({source.query for source in evidence if source.query})
        corrected_fact = normalize_corrected_fact(data.get("corrected_fact"))
        return ClaimVerdict(
            claim=claim,
            verdict=normalize_claim_verdict(data.get("verdict"), corrected_fact),
            corrected_fact=corrected_fact,
            confidence=normalize_confidence(data.get("confidence")),
            reasoning=data.get("reasoning")
            or "The model returned an incomplete verdict, so this result is low confidence.",
            sources=evidence,
            search_queries=search_queries,
        )
