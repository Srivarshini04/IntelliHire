"""Unit tests — SummaryComposer (recruiter-facing reasoning summaries)."""

from __future__ import annotations

import copy

import pytest

from app.intelligence.reasoning.claim_synthesizer import ClaimSynthesizer
from app.intelligence.reasoning.types import MaterialityMap
from app.mock import load_graph, load_role_dna
from app.intelligence.reasoning.confidence_engine import ConfidenceEngine, ConfidenceResult
from app.intelligence.reasoning.gap_analyzer import GapAnalysis, GapAnalyzer, GapItem
from app.intelligence.reasoning.summary_composer import ReasoningSummary, SummaryComposer
from app.intelligence.reasoning.uncertainty_detector import UncertaintyAnalysis, UncertaintyItem
from app.shared.enums import Intensity
from app.shared.models import ReasoningClaim


@pytest.fixture
def composer() -> SummaryComposer:
    return SummaryComposer()


def _claim(
    claim_id: str,
    *,
    statement: str = "Statement",
    conclusion: str = "Conclusion",
    confidence: float = 0.85,
    supporting: list[str] | None = None,
    counter: list[str] | None = None,
    materiality: Intensity = Intensity.HIGH,
) -> ReasoningClaim:
    return ReasoningClaim(
        claim_id=claim_id,
        statement=statement,
        entity_refs=[f"skill:{claim_id}"],
        supporting_evidence_ids=supporting or ["ev_1"],
        counter_evidence_ids=counter or [],
        confidence=confidence,
        materiality=materiality,
        conclusion=conclusion,
    )


def _gap(severity: str, title: str, rationale: str) -> GapItem:
    return GapItem(
        category="must_have",
        title=title,
        severity=severity,
        rationale=rationale,
        missing_evidence=[f"skill:{title.lower()}"],
    )


def _uncertainty(severity: str, title: str, rationale: str) -> UncertaintyItem:
    return UncertaintyItem(
        category="gap",
        title=title,
        severity=severity,
        rationale=rationale,
        related_entities=[f"skill:{title.lower()}"],
        evidence_count=1,
    )


def _confidence(overall: float = 0.82) -> ConfidenceResult:
    return ConfidenceResult(
        overall_confidence=overall,
        claim_confidence=0.85,
        evidence_confidence=0.75,
        uncertainty_penalty=0.1,
        explanation="Test confidence explanation.",
    )


def test_normal_summary_includes_all_sections(composer: SummaryComposer) -> None:
    claims = [
        _claim("python", conclusion="Strong Python across sources."),
        _claim("retrieval", conclusion="Production retrieval experience."),
    ]
    gaps = GapAnalysis(moderate=[_gap("moderate", "Vector", "Missing vector DB depth.")])
    uncertainties = UncertaintyAnalysis(
        medium=[_uncertainty("medium", "Eval", "Sparse evaluation corroboration.")]
    )
    result = composer.compose(claims, gaps, uncertainties, _confidence())

    assert len(result.strengths) == 2
    assert len(result.gaps) == 1
    assert len(result.uncertainties) == 1
    assert result.confidence_text
    assert result.overall_summary


def test_empty_inputs_produce_empty_lists(composer: SummaryComposer) -> None:
    result = composer.compose([], GapAnalysis(), UncertaintyAnalysis(), _confidence())
    assert result.strengths == []
    assert result.gaps == []
    assert result.uncertainties == []
    assert result.confidence_text
    assert result.overall_summary == result.confidence_text


def test_no_strengths_when_claims_lack_support(composer: SummaryComposer) -> None:
    claims = [
        ReasoningClaim(
            claim_id="c1",
            statement="Claims skill",
            entity_refs=["skill:x"],
            supporting_evidence_ids=[],
            counter_evidence_ids=["ev_c"],
            confidence=0.4,
            conclusion="Unsubstantiated claim.",
        )
    ]
    result = composer.compose(claims, GapAnalysis(), UncertaintyAnalysis(), _confidence())
    assert result.strengths == []


def test_no_gaps_section_empty(composer: SummaryComposer) -> None:
    result = composer.compose(
        [_claim("a", conclusion="Strength.")],
        GapAnalysis(),
        UncertaintyAnalysis(),
        _confidence(),
    )
    assert result.gaps == []
    assert "Gaps to probe" not in result.overall_summary


def test_no_uncertainties_section_empty(composer: SummaryComposer) -> None:
    result = composer.compose(
        [_claim("a", conclusion="Strength.")],
        GapAnalysis(),
        UncertaintyAnalysis(),
        _confidence(),
    )
    assert result.uncertainties == []
    assert "Uncertainties" not in result.overall_summary


def test_deterministic_output(composer: SummaryComposer) -> None:
    claims = [_claim("b", conclusion="B"), _claim("a", conclusion="A")]
    gaps = GapAnalysis(critical=[_gap("critical", "Python", "No Python evidence.")])
    uncertainties = UncertaintyAnalysis(low=[_uncertainty("low", "K8s", "Optional gap.")])
    confidence = _confidence()

    first = composer.compose(claims, gaps, uncertainties, confidence)
    second = composer.compose(claims, gaps, uncertainties, confidence)
    assert first == second


def test_strengths_sorted_by_materiality_then_confidence(composer: SummaryComposer) -> None:
    claims = [
        _claim("low", conclusion="Low priority", materiality=Intensity.LOW, confidence=0.95),
        _claim("critical", conclusion="Critical fit", materiality=Intensity.CRITICAL, confidence=0.8),
        _claim("high", conclusion="High fit", materiality=Intensity.HIGH, confidence=0.9),
    ]
    result = composer.compose(claims, GapAnalysis(), UncertaintyAnalysis(), _confidence())
    assert result.strengths[0] == "Critical fit"


def test_gaps_sorted_by_severity(composer: SummaryComposer) -> None:
    gaps = GapAnalysis(
        minor=[_gap("minor", "K8s", "Minor gap.")],
        critical=[_gap("critical", "Python", "Critical gap.")],
        moderate=[_gap("moderate", "Vector", "Moderate gap.")],
    )
    result = composer.compose([], gaps, UncertaintyAnalysis(), _confidence())
    assert result.gaps[0] == "Critical gap."


def test_uncertainties_sorted_by_severity(composer: SummaryComposer) -> None:
    uncertainties = UncertaintyAnalysis(
        low=[_uncertainty("low", "Nice", "Low uncertainty.")],
        high=[_uncertainty("high", "Conflict", "High uncertainty.")],
        medium=[_uncertainty("medium", "Sparse", "Medium uncertainty.")],
    )
    result = composer.compose([], GapAnalysis(), uncertainties, _confidence())
    assert result.uncertainties[0] == "High uncertainty."


def test_duplicate_strength_text_removed(composer: SummaryComposer) -> None:
    claims = [
        _claim("a", conclusion="Same text."),
        _claim("b", conclusion="Same text."),
    ]
    result = composer.compose(claims, GapAnalysis(), UncertaintyAnalysis(), _confidence())
    assert result.strengths == ["Same text."]


def test_section_limited_to_five_items(composer: SummaryComposer) -> None:
    claims = [_claim(f"c{i}", conclusion=f"Strength {i}.") for i in range(8)]
    result = composer.compose(claims, GapAnalysis(), UncertaintyAnalysis(), _confidence())
    assert len(result.strengths) == 5


def test_confidence_text_includes_score_and_level(composer: SummaryComposer) -> None:
    high = composer.compose([], GapAnalysis(), UncertaintyAnalysis(), _confidence(0.9))
    moderate = composer.compose([], GapAnalysis(), UncertaintyAnalysis(), _confidence(0.65))
    low = composer.compose([], GapAnalysis(), UncertaintyAnalysis(), _confidence(0.4))

    assert "0.90" in high.confidence_text
    assert "(high)" in high.confidence_text
    assert "(moderate)" in moderate.confidence_text
    assert "(low)" in low.confidence_text


def test_confidence_text_includes_explanation(composer: SummaryComposer) -> None:
    result = composer.compose([], GapAnalysis(), UncertaintyAnalysis(), _confidence())
    assert "Test confidence explanation." in result.confidence_text


def test_overall_summary_mentions_strengths_and_gaps(composer: SummaryComposer) -> None:
    result = composer.compose(
        [_claim("a", conclusion="Strong Python.")],
        GapAnalysis(moderate=[_gap("moderate", "Vector", "Vector DB gap.")]),
        UncertaintyAnalysis(),
        _confidence(),
    )
    assert "Strengths" in result.overall_summary
    assert "Gaps to probe" in result.overall_summary
    assert "Strong Python." in result.overall_summary


def test_inputs_not_mutated(composer: SummaryComposer) -> None:
    claims = [_claim("a", conclusion="Strength.")]
    gaps = GapAnalysis(minor=[_gap("minor", "K8s", "Minor gap.")])
    uncertainties = UncertaintyAnalysis(low=[_uncertainty("low", "Nice", "Low uncertainty.")])
    confidence = _confidence()

    claims_before = [c.model_dump() for c in claims]
    gaps_before = copy.deepcopy(gaps)
    uncertainties_before = copy.deepcopy(uncertainties)
    confidence_before = copy.deepcopy(confidence)

    composer.compose(claims, gaps, uncertainties, confidence)

    assert [c.model_dump() for c in claims] == claims_before
    assert gaps == gaps_before
    assert uncertainties == uncertainties_before
    assert confidence == confidence_before


def test_contradiction_dominated_claim_excluded_from_strengths(composer: SummaryComposer) -> None:
    claims = [
        _claim(
            "finetuning",
            conclusion="Unsubstantiated fine-tuning.",
            supporting=[],
            counter=["ev_c", "ev_d"],
        )
    ]
    result = composer.compose(claims, GapAnalysis(), UncertaintyAnalysis(), _confidence())
    assert result.strengths == []


def test_uses_conclusion_over_statement_for_strengths(composer: SummaryComposer) -> None:
    claims = [_claim("a", statement="Raw statement", conclusion="Recruiter conclusion.")]
    result = composer.compose(claims, GapAnalysis(), UncertaintyAnalysis(), _confidence())
    assert result.strengths == ["Recruiter conclusion."]


def test_gap_falls_back_to_title_when_rationale_empty(composer: SummaryComposer) -> None:
    gap = GapItem(
        category="must_have",
        title="Vector Search",
        severity="moderate",
        rationale="",
        missing_evidence=["skill:vector_search"],
    )
    result = composer.compose([], GapAnalysis(moderate=[gap]), UncertaintyAnalysis(), _confidence())
    assert result.gaps == ["Vector Search"]


def test_reasoning_summary_is_dataclass(composer: SummaryComposer) -> None:
    result = composer.compose([], GapAnalysis(), UncertaintyAnalysis(), _confidence())
    assert isinstance(result, ReasoningSummary)


def test_mock_fixture_end_to_end_summary(composer: SummaryComposer) -> None:
    graph = load_graph()
    role = load_role_dna()
    claims = ClaimSynthesizer().synthesize(graph, MaterialityMap(), role)
    gaps = GapAnalyzer().analyze(graph, role, claims)
    from app.intelligence.reasoning.uncertainty_detector import UncertaintyDetector

    uncertainties = UncertaintyDetector().detect(graph, role, claims, gaps)
    confidence = ConfidenceEngine().compute(claims, gaps, uncertainties)
    result = composer.compose(claims, gaps, uncertainties, confidence)

    assert result.strengths
    assert result.gaps or result.uncertainties
    assert result.overall_summary
    assert "Overall reasoning confidence" in result.confidence_text


def test_copy_produces_same_summary(composer: SummaryComposer) -> None:
    claims = [_claim("a", conclusion="Strength.")]
    gaps = GapAnalysis(moderate=[_gap("moderate", "Vector", "Gap text.")])
    uncertainties = UncertaintyAnalysis(medium=[_uncertainty("medium", "Sparse", "Unc text.")])
    confidence = _confidence()

    first = composer.compose(claims, gaps, uncertainties, confidence)
    second = composer.compose(
        [ReasoningClaim.model_validate(c.model_dump()) for c in claims],
        copy.deepcopy(gaps),
        copy.deepcopy(uncertainties),
        ConfidenceResult(**copy.deepcopy(confidence.__dict__)),
    )
    assert first == second


def test_overall_summary_includes_uncertainties_when_present(composer: SummaryComposer) -> None:
    result = composer.compose(
        [],
        GapAnalysis(),
        UncertaintyAnalysis(high=[_uncertainty("high", "Conflict", "Conflicting signal.")]),
        _confidence(),
    )
    assert "Uncertainties" in result.overall_summary
    assert "Conflicting signal." in result.overall_summary


def test_no_placeholder_text_for_empty_sections(composer: SummaryComposer) -> None:
    result = composer.compose([], GapAnalysis(), UncertaintyAnalysis(), _confidence())
    assert result.strengths == []
    assert "N/A" not in result.overall_summary
    assert "none" not in result.overall_summary.lower()


def test_strength_uses_statement_when_conclusion_blank(composer: SummaryComposer) -> None:
    claim = ReasoningClaim(
        claim_id="a",
        statement="Fallback statement.",
        entity_refs=["skill:a"],
        supporting_evidence_ids=["ev_1"],
        confidence=0.8,
        conclusion="",
    )
    result = composer.compose([claim], GapAnalysis(), UncertaintyAnalysis(), _confidence())
    assert result.strengths == ["Fallback statement."]
