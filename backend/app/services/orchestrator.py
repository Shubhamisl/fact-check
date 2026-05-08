from app.config import Settings, get_settings
from app.models import (
    ClaimVerdict,
    EvidenceSource,
    ExtractedClaim,
    FactCheckReport,
    PageText,
    ScanMode,
)
from app.services.claim_extractor import ClaimExtractor
from app.services.claim_grouper import build_report_summary, group_claims
from app.services.search_service import gather_evidence_for_group
from app.services.tavily_client import TavilyClient
from app.services.verifier import Verifier


class DefaultSearchService:
    def __init__(self, tavily_client: TavilyClient | None = None) -> None:
        settings = get_settings()
        self.tavily_client = tavily_client or TavilyClient(
            api_key=settings.tavily_api_key,
            search_depth=settings.tavily_search_depth,
        )

    async def gather_evidence_for_group(
        self,
        topic: str,
        claims: list[ExtractedClaim],
    ) -> list[EvidenceSource]:
        return await gather_evidence_for_group(self.tavily_client, topic, claims)

    async def follow_up(self, claim: ExtractedClaim) -> list[EvidenceSource]:
        return await gather_evidence_for_group(
            self.tavily_client,
            claim.topic,
            [claim],
            max_results_per_query=5,
        )


class FactCheckOrchestrator:
    def __init__(
        self,
        claim_extractor: ClaimExtractor | None = None,
        search_service: DefaultSearchService | None = None,
        verifier: Verifier | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.claim_extractor = claim_extractor or ClaimExtractor()
        self.search_service = search_service or DefaultSearchService()
        self.verifier = verifier or Verifier()

    async def run(
        self,
        file_name: str,
        pages: list[PageText],
        mode: ScanMode,
    ) -> FactCheckReport:
        claim_limit = self.settings.claim_limit_for_mode(mode.value)
        claims = await self.claim_extractor.extract_claims(pages, mode, claim_limit)
        grouped_claims = group_claims(claims)
        verdicts: list[ClaimVerdict] = []

        for topic, topic_claims in grouped_claims.items():
            evidence = await self.search_service.gather_evidence_for_group(
                topic,
                topic_claims,
            )
            for claim in topic_claims:
                verdict = await self.verifier.verify(claim, evidence)
                if verdict.confidence == "Low" and claim.importance == "high":
                    follow_up = await self.search_service.follow_up(claim)
                    if follow_up:
                        verdict = await self.verifier.verify(
                            claim,
                            evidence + follow_up,
                        )
                verdicts.append(verdict)

        return FactCheckReport(
            file_name=file_name,
            scan_mode=mode,
            summary=build_report_summary([verdict.verdict for verdict in verdicts]),
            claims=verdicts,
        )
