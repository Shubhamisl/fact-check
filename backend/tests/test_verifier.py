import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import EvidenceSource, ExtractedClaim
from app.services.verifier import Verifier


class IncompleteOpenRouterClient:
    async def chat_json(self, system: str, user: str, model: str | None = None):
        return {"verdict": "unsupported"}


@pytest.mark.asyncio
async def test_verifier_defaults_incomplete_model_verdicts_to_low_confidence():
    claim = ExtractedClaim(
        id="claim-1",
        text="The Eiffel Tower is 10,000 meters tall.",
        page_number=1,
        claim_type="statistic",
        topic="Eiffel Tower",
        importance="high",
    )
    evidence = [
        EvidenceSource(
            title="Official page",
            url="https://example.com/eiffel",
            snippet="The tower is much shorter than 10,000 meters.",
            query="Eiffel Tower height",
        )
    ]

    verdict = await Verifier(IncompleteOpenRouterClient()).verify(claim, evidence)

    assert verdict.verdict == "False / Unsupported"
    assert verdict.confidence == "Low"
    assert "incomplete verdict" in verdict.reasoning
    assert verdict.search_queries == ["Eiffel Tower height"]
