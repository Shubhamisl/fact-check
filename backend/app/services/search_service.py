from app.models import EvidenceSource, ExtractedClaim
from app.services.tavily_client import TavilyClient


def build_search_queries(
    topic: str,
    claims: list[ExtractedClaim],
    max_queries: int = 2,
) -> list[str]:
    queries: list[str] = []

    for claim in claims:
        snippet = claim.text.strip()[:160]
        if snippet:
            queries.append(f"{snippet} source")
        if len(queries) >= max_queries:
            return queries

    topic = topic.strip()
    if topic:
        queries.append(f"{topic} latest official data")

    return queries[:max_queries]


def normalize_tavily_results(raw: dict, query: str) -> list[EvidenceSource]:
    evidence: list[EvidenceSource] = []

    for item in raw.get("results", []):
        url = item.get("url")
        if not url:
            continue

        evidence.append(
            EvidenceSource(
                title=item.get("title") or "Untitled source",
                url=url,
                snippet=item.get("content") or item.get("snippet") or "",
                published_date=item.get("published_date"),
                query=query,
            )
        )

    return evidence


async def gather_evidence_for_group(
    tavily_client: TavilyClient,
    topic: str,
    claims: list[ExtractedClaim],
    max_results_per_query: int = 3,
    max_queries: int = 2,
) -> list[EvidenceSource]:
    evidence: list[EvidenceSource] = []

    for query in build_search_queries(topic, claims, max_queries=max_queries):
        raw = await tavily_client.search(query, max_results=max_results_per_query)
        evidence.extend(normalize_tavily_results(raw, query))

    return evidence
