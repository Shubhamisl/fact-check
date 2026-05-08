from app.models import EvidenceSource, ExtractedClaim
from app.services.tavily_client import TavilyClient


def build_search_queries(topic: str, claims: list[ExtractedClaim]) -> list[str]:
    queries = [f"{topic} latest official data"]

    for claim in claims[:3]:
        snippet = claim.text.strip()[:160]
        if snippet:
            queries.append(f"{snippet} source")

    return queries


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
) -> list[EvidenceSource]:
    evidence: list[EvidenceSource] = []

    for query in build_search_queries(topic, claims):
        raw = await tavily_client.search(query, max_results=max_results_per_query)
        evidence.extend(normalize_tavily_results(raw, query))

    return evidence
