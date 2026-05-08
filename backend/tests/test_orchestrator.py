import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import ClaimVerdict, EvidenceSource, ExtractedClaim, PageText, ScanMode
from app.services.orchestrator import FactCheckOrchestrator


def _claim() -> ExtractedClaim:
    return ExtractedClaim(
        id="claim-1",
        text="The platform has 10 million users.",
        page_number=1,
        claim_type="metric",
        topic="platform users",
        importance="high",
    )


def _evidence() -> EvidenceSource:
    return EvidenceSource(
        title="Company metrics",
        url="https://example.com/company-metrics",
        snippet="The platform has 8 million users.",
        query="platform users latest official data",
    )


class FakeClaimExtractor:
    def __init__(self) -> None:
        self.calls: list[tuple[list[PageText], ScanMode, int]] = []

    async def extract_claims(
        self,
        pages: list[PageText],
        mode: ScanMode,
        limit: int,
    ) -> list[ExtractedClaim]:
        self.calls.append((pages, mode, limit))
        return [_claim()]


class EmptyClaimExtractor(FakeClaimExtractor):
    async def extract_claims(
        self,
        pages: list[PageText],
        mode: ScanMode,
        limit: int,
    ) -> list[ExtractedClaim]:
        self.calls.append((pages, mode, limit))
        return []


class FakeSearchService:
    def __init__(self) -> None:
        self.group_calls: list[tuple[str, list[ExtractedClaim]]] = []
        self.follow_up_calls: list[ExtractedClaim] = []

    async def gather_evidence_for_group(
        self,
        topic: str,
        claims: list[ExtractedClaim],
    ) -> list[EvidenceSource]:
        self.group_calls.append((topic, claims))
        return [_evidence()]

    async def follow_up(self, claim: ExtractedClaim) -> list[EvidenceSource]:
        self.follow_up_calls.append(claim)
        return []


class FailingGatherSearchService(FakeSearchService):
    async def gather_evidence_for_group(
        self,
        topic: str,
        claims: list[ExtractedClaim],
    ) -> list[EvidenceSource]:
        self.group_calls.append((topic, claims))
        raise RuntimeError("tavily unavailable")


class FailingFollowUpSearchService(FakeSearchService):
    async def follow_up(self, claim: ExtractedClaim) -> list[EvidenceSource]:
        self.follow_up_calls.append(claim)
        raise RuntimeError("tavily unavailable")


class FakeVerifier:
    def __init__(self) -> None:
        self.calls: list[tuple[ExtractedClaim, list[EvidenceSource]]] = []

    async def verify(
        self,
        claim: ExtractedClaim,
        evidence: list[EvidenceSource],
    ) -> ClaimVerdict:
        self.calls.append((claim, evidence))
        return ClaimVerdict(
            claim=claim,
            verdict="Inaccurate",
            corrected_fact="The platform has 8 million users.",
            confidence="High",
            reasoning="The supplied evidence reports 8 million users.",
            sources=evidence,
            search_queries=[source.query for source in evidence],
        )


class LowConfidenceVerifier(FakeVerifier):
    async def verify(
        self,
        claim: ExtractedClaim,
        evidence: list[EvidenceSource],
    ) -> ClaimVerdict:
        self.calls.append((claim, evidence))
        return ClaimVerdict(
            claim=claim,
            verdict="False / Unsupported",
            corrected_fact=None,
            confidence="Low",
            reasoning="The evidence is insufficient to verify the claim.",
            sources=evidence,
            search_queries=[source.query for source in evidence],
        )


class FakeSettings:
    enable_follow_up_search = True

    def claim_limit_for_mode(self, mode: str) -> int:
        assert mode == "focused"
        return 1


@pytest.mark.asyncio
async def test_orchestrator_returns_report_summary_and_corrected_fact_for_one_claim():
    pages = [
        PageText(
            page_number=1,
            text="The platform has 10 million users.",
            source="pdf",
        )
    ]
    extractor = FakeClaimExtractor()
    search_service = FakeSearchService()
    verifier = FakeVerifier()
    orchestrator = FactCheckOrchestrator(
        claim_extractor=extractor,
        search_service=search_service,
        verifier=verifier,
        settings=FakeSettings(),
    )

    report = await orchestrator.run("deck.pdf", pages, ScanMode.focused)

    assert report.file_name == "deck.pdf"
    assert report.scan_mode == ScanMode.focused
    assert report.summary == {
        "total": 1,
        "verified": 0,
        "inaccurate": 1,
        "false_or_unsupported": 0,
    }
    assert len(report.claims) == 1
    assert report.claims[0].corrected_fact == "The platform has 8 million users."
    assert extractor.calls == [(pages, ScanMode.focused, 1)]
    assert search_service.group_calls[0][0] == "platform users"
    assert verifier.calls[0][0].id == "claim-1"


@pytest.mark.asyncio
async def test_gather_failure_marks_claim_verification_unavailable_without_run_failure():
    pages = [
        PageText(
            page_number=1,
            text="The platform has 10 million users.",
            source="pdf",
        )
    ]
    search_service = FailingGatherSearchService()
    verifier = FakeVerifier()
    orchestrator = FactCheckOrchestrator(
        claim_extractor=FakeClaimExtractor(),
        search_service=search_service,
        verifier=verifier,
        settings=FakeSettings(),
    )

    report = await orchestrator.run("deck.pdf", pages, ScanMode.focused)

    assert report.summary == {
        "total": 1,
        "verified": 0,
        "inaccurate": 0,
        "false_or_unsupported": 1,
    }
    assert len(report.claims) == 1
    verdict = report.claims[0]
    assert verdict.verdict == "False / Unsupported"
    assert verdict.corrected_fact is None
    assert verdict.confidence == "Low"
    assert "evidence search failed" in verdict.reasoning
    assert "verification is unavailable" in verdict.reasoning
    assert verdict.sources == []
    assert verdict.search_queries == []
    assert verifier.calls == []


@pytest.mark.asyncio
async def test_empty_extraction_returns_unsupported_report_without_searching():
    pages = [
        PageText(
            page_number=1,
            text="The platform has 10 million users.",
            source="pdf",
        )
    ]
    search_service = FakeSearchService()
    verifier = FakeVerifier()
    orchestrator = FactCheckOrchestrator(
        claim_extractor=EmptyClaimExtractor(),
        search_service=search_service,
        verifier=verifier,
        settings=FakeSettings(),
    )

    report = await orchestrator.run("deck.pdf", pages, ScanMode.focused)

    assert report.summary == {
        "total": 1,
        "verified": 0,
        "inaccurate": 0,
        "false_or_unsupported": 1,
    }
    assert report.claims[0].claim.id == "claim-extraction-unavailable"
    assert report.claims[0].confidence == "Low"
    assert "did not return any valid structured claims" in report.claims[0].reasoning
    assert search_service.group_calls == []
    assert verifier.calls == []


@pytest.mark.asyncio
async def test_follow_up_failure_preserves_original_low_confidence_verdict():
    pages = [
        PageText(
            page_number=1,
            text="The platform has 10 million users.",
            source="pdf",
        )
    ]
    search_service = FailingFollowUpSearchService()
    verifier = LowConfidenceVerifier()
    orchestrator = FactCheckOrchestrator(
        claim_extractor=FakeClaimExtractor(),
        search_service=search_service,
        verifier=verifier,
        settings=FakeSettings(),
    )

    report = await orchestrator.run("deck.pdf", pages, ScanMode.focused)

    assert len(report.claims) == 1
    verdict = report.claims[0]
    assert verdict.verdict == "False / Unsupported"
    assert verdict.confidence == "Low"
    assert verdict.reasoning == "The evidence is insufficient to verify the claim."
    assert len(verifier.calls) == 1
    assert len(search_service.follow_up_calls) == 1
