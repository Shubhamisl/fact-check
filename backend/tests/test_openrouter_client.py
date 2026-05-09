import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.openrouter_client import OpenRouterClient


class FencedJsonOpenRouterClient(OpenRouterClient):
    async def chat_text(
        self,
        system: str,
        user: str,
        model: str | None = None,
    ) -> str:
        return '```json\n{"claims": [{"id": "claim-1"}]}\n```'


@pytest.mark.asyncio
async def test_chat_json_accepts_fenced_json_response():
    data = await FencedJsonOpenRouterClient(api_key="key").chat_json(
        system="Return JSON.",
        user="Extract claims.",
    )

    assert data == {"claims": [{"id": "claim-1"}]}
