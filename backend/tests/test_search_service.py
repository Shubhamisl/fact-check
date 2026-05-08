import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import ExtractedClaim
from app.services.search_service import (
    build_search_queries,
    gather_evidence_for_group,
    normalize_tavily_results,
)
from app.services.tavily_client import TavilyClient


def _claim(
    id_: str = "claim-1",
    text: str = "The global AI market reached $500 billion in 2024.",
    topic: str = "Global AI market",
) -> ExtractedClaim:
    return ExtractedClaim(
        id=id_,
        text=text,
        page_number=1,
        claim_type="metric",
        topic=topic,
        importance="high",
    )


def test_build_search_queries_uses_topic_latest_official_data_and_claim_source_query():
    queries = build_search_queries("Global AI market", [_claim()])

    assert queries[0] == "Global AI market latest official data"
    assert "The global AI market reached $500 billion in 2024." in queries[1]
    assert "source" in queries[1]


def test_normalize_tavily_results_keeps_title_url_snippet_published_date_and_query():
    raw = {
        "results": [
            {
                "title": "AI market report",
                "url": "https://example.com/ai-market",
                "content": "The report says the market is growing quickly.",
                "published_date": "2024-10-02",
            }
        ]
    }

    evidence = normalize_tavily_results(raw, query="market query")

    assert len(evidence) == 1
    assert evidence[0].title == "AI market report"
    assert str(evidence[0].url) == "https://example.com/ai-market"
    assert evidence[0].snippet == "The report says the market is growing quickly."
    assert evidence[0].published_date == "2024-10-02"
    assert evidence[0].query == "market query"


def test_normalize_tavily_results_uses_snippet_fallback_and_skips_items_without_url():
    raw = {
        "results": [
            {"title": "Missing URL", "content": "No source link"},
            {
                "title": "Snippet result",
                "url": "https://example.com/snippet",
                "snippet": "Snippet fallback text.",
            },
        ]
    }

    evidence = normalize_tavily_results(raw, query="query")

    assert len(evidence) == 1
    assert evidence[0].snippet == "Snippet fallback text."
    assert str(evidence[0].url) == "https://example.com/snippet"


@pytest.mark.asyncio
async def test_gather_evidence_for_group_searches_each_query_and_normalizes_results():
    class FakeTavilyClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, int]] = []

        async def search(self, query: str, max_results: int = 5) -> dict:
            self.calls.append((query, max_results))
            return {
                "results": [
                    {
                        "title": f"Result for {query}",
                        "url": f"https://example.com/{len(self.calls)}",
                        "content": "Evidence text",
                    }
                ]
            }

    client = FakeTavilyClient()

    evidence = await gather_evidence_for_group(
        client,
        "Global AI market",
        [_claim()],
        max_results_per_query=3,
    )

    assert len(client.calls) == 2
    assert all(max_results == 3 for _, max_results in client.calls)
    assert [source.query for source in evidence] == [query for query, _ in client.calls]


@pytest.mark.asyncio
async def test_tavily_client_posts_search_request_and_returns_json(monkeypatch):
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            captured["raised"] = True

        def json(self) -> dict:
            return {"results": [{"title": "Result"}]}

    class FakeAsyncClient:
        def __init__(self, timeout: int) -> None:
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def post(
            self, url: str, json: dict, headers: dict[str, str]
        ) -> FakeResponse:
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    result = await TavilyClient(api_key="tv-key", search_depth="advanced").search(
        "AI market",
        max_results=7,
    )

    assert result == {"results": [{"title": "Result"}]}
    assert captured["timeout"] == 30
    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["raised"] is True
    assert captured["headers"] == {"Authorization": "Bearer tv-key"}
    assert "api_key" not in captured["json"]
    assert captured["json"] == {
        "query": "AI market",
        "search_depth": "advanced",
        "max_results": 7,
        "include_answer": False,
        "include_raw_content": False,
    }
