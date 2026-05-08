import re

from app.models import ExtractedClaim, VerdictLabel


def normalize_topic(topic: str) -> str:
    normalized = re.sub(r"\s+", " ", topic.strip().lower())
    return normalized or "general"


def group_claims(claims: list[ExtractedClaim]) -> dict[str, list[ExtractedClaim]]:
    grouped: dict[str, list[ExtractedClaim]] = {}

    for claim in claims:
        topic = normalize_topic(claim.topic)
        grouped.setdefault(topic, []).append(claim)

    return grouped


def build_report_summary(verdicts: list[VerdictLabel]) -> dict[str, int]:
    return {
        "total": len(verdicts),
        "verified": verdicts.count("Verified"),
        "inaccurate": verdicts.count("Inaccurate"),
        "false_or_unsupported": verdicts.count("False / Unsupported"),
    }
