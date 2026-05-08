import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import ExtractedClaim
from app.services.claim_grouper import build_report_summary, group_claims, normalize_topic


def make_claim(claim_id: str, topic: str) -> ExtractedClaim:
    return ExtractedClaim(
        id=claim_id,
        text=f"Claim {claim_id}",
        claim_type="metric",
        topic=topic,
    )


def test_normalize_topic_lowercases_strips_collapses_whitespace_and_defaults_to_general():
    assert normalize_topic("  Global   AI\tMarket  ") == "global ai market"
    assert normalize_topic("   ") == "general"


def test_group_claims_normalizes_topic_names_and_preserves_insertion_order():
    grouped = group_claims(
        [
            make_claim("c1", "Global AI Market"),
            make_claim("c2", "global ai market "),
            make_claim("c3", "Customer Count"),
        ]
    )

    assert list(grouped.keys()) == ["global ai market", "customer count"]
    assert [claim.id for claim in grouped["global ai market"]] == ["c1", "c2"]


def test_build_report_summary_counts_verdict_labels():
    assert build_report_summary(
        ["Verified", "Verified", "Inaccurate", "False / Unsupported"]
    ) == {
        "total": 4,
        "verified": 2,
        "inaccurate": 1,
        "false_or_unsupported": 1,
    }
