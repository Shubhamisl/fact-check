import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import PageText, ScanMode
from app.services.claim_extractor import ClaimExtractor


class FakeOpenRouterClient:
    async def chat_json(self, system: str, user: str, model: str | None = None):
        return {
            "claims": [
                {"": None},
                {
                    "id": "claim-1",
                    "text": "OpenAI released GPT-4 in March 2023.",
                    "page_number": 1,
                    "claim_type": "date",
                    "topic": "GPT-4 release",
                    "importance": "high",
                },
            ]
        }


@pytest.mark.asyncio
async def test_claim_extractor_skips_malformed_claim_items():
    extractor = ClaimExtractor(FakeOpenRouterClient())

    claims = await extractor.extract_claims(
        [PageText(page_number=1, text="OpenAI released GPT-4 in March 2023.", source="pdf")],
        ScanMode.focused,
        limit=5,
    )

    assert len(claims) == 1
    assert claims[0].id == "claim-1"


class MalformedOnlyOpenRouterClient:
    async def chat_json(self, system: str, user: str, model: str | None = None):
        return {"claims": [{"": None}]}


@pytest.mark.asyncio
async def test_claim_extractor_falls_back_to_regex_claims_when_model_schema_fails():
    extractor = ClaimExtractor(MalformedOnlyOpenRouterClient())

    claims = await extractor.extract_claims(
        [
            PageText(
                page_number=1,
                text=(
                    "The United States population was 500 million people in 2024. "
                    "The Eiffel Tower is 10,000 meters tall."
                ),
                source="pdf",
            )
        ],
        ScanMode.focused,
        limit=5,
    )

    assert [claim.text for claim in claims] == [
        "The United States population was 500 million people in 2024.",
        "The Eiffel Tower is 10,000 meters tall.",
    ]
    assert claims[0].claim_type == "date"
    assert claims[0].page_number == 1
