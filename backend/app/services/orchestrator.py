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
        self.settings = get_settings()
        self.tavily_client = tavily_client or TavilyClient(
            api_key=self.settings.tavily_api_key,
            search_depth=self.settings.tavily_search_depth,
        )

    async def gather_evidence_for_group(
        self,
        topic: str,
        claims: list[ExtractedClaim],
    ) -> list[EvidenceSource]:
        return await gather_evidence_for_group(
            self.tavily_client,
            topic,
            claims,
            max_results_per_query=self.settings.max_search_results_per_query,
            max_queries=self.settings.max_search_queries_per_group,
        )

    async def follow_up(self, claim: ExtractedClaim) -> list[EvidenceSource]:
        if not self.settings.enable_follow_up_search:
            return []
        return await gather_evidence_for_group(
            self.tavily_client,
            claim.topic,
            [claim],
            max_results_per_query=self.settings.max_search_results_per_query,
            max_queries=1,
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
        if not claims:
            fallback_claim = ExtractedClaim(
                id="claim-extraction-unavailable",
                text="No valid structured claims could be extracted from this PDF.",
                page_number=None,
                claim_type="extraction_error",
                topic="claim extraction",
                importance="high",
            )
            verdict = ClaimVerdict(
                claim=fallback_claim,
                verdict="False / Unsupported",
                corrected_fact=None,
                confidence="Low",
                reasoning=(
                    "The model did not return any valid structured claims. Try a "
                    "model with stronger JSON/structured-output support or run "
                    "Deep Scan."
                ),
                sources=[],
                search_queries=[],
            )
            return FactCheckReport(
                file_name=file_name,
                scan_mode=mode,
                summary=build_report_summary([verdict.verdict]),
                claims=[verdict],
            )

        grouped_claims = group_claims(claims)
        verdicts: list[ClaimVerdict] = []

        for topic, topic_claims in grouped_claims.items():
            try:
                evidence = await self.search_service.gather_evidence_for_group(
                    topic,
                    topic_claims,
                )
            except Exception:
                verdicts.extend(
                    ClaimVerdict(
                        claim=claim,
                        verdict="False / Unsupported",
                        corrected_fact=None,
                        confidence="Low",
                        reasoning=(
                            "evidence search failed, so verification is unavailable "
                            "for this claim."
                        ),
                        sources=[],
                        search_queries=[],
                    )
                    for claim in topic_claims
                )
                continue

            for claim in topic_claims:
                try:
                    verdict = await self.verifier.verify(claim, evidence)
                except Exception:
                    verdicts.append(
                        ClaimVerdict(
                            claim=claim,
                            verdict="False / Unsupported",
                            corrected_fact=None,
                            confidence="Low",
                            reasoning=(
                                "verification model failed, so verification is "
                                "unavailable for this claim."
                            ),
                            sources=evidence,
                            search_queries=sorted(
                                {source.query for source in evidence if source.query}
                            ),
                        )
                    )
                    continue
                if (
                    self.settings.enable_follow_up_search
                    and verdict.confidence == "Low"
                    and claim.importance == "high"
                ):
                    try:
                        follow_up = await self.search_service.follow_up(claim)
                    except Exception:
                        follow_up = []
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
