"""Unit tests — DecisionEngine (deterministic hiring recommendations)."""

from __future__ import annotations

import copy

import pytest

from app.mock import load_graph, load_role_dna
from app.intelligence.decision.decision_engine import DecisionEngine, DecisionResult, Recommendation
from app.intelligence.reasoning.confidence_engine import ConfidenceResult
from app.intelligence.reasoning.gap_analyzer import GapAnalysis, GapItem
from app.intelligence.reasoning.reasoning_engine import ReasoningEngine, ReasoningResult
from app.intelligence.reasoning.summary_composer import ReasoningSummary
from app.intelligence.reasoning.uncertainty_detector import UncertaintyAnalysis, UncertaintyItem
from app.shared.enums import Intensity
from app.shared.models import ReasoningClaim


@pytest.fixture
def engine() -> DecisionEngine:
    return DecisionEngine()


def _claim(
    claim_id: str = "c1",
    *,
    confidence: float = 0.9,
    supporting: list[str] | None = None,
) -> ReasoningClaim:
    return ReasoningClaim(
        claim_id=claim_id,
        statement="Statement",
        entity_refs=[f"skill:{claim_id}"],
        supporting_evidence_ids=supporting or ["ev_1"],
        confidence=confidence,
        materiality=Intensity.CRITICAL,
        conclusion="Strong competency.",
    )


def _gap(severity: str, title: str, rationale: str = "") -> GapItem:
    return GapItem(
        category="must_have",
        title=title,
        severity=severity,
        rationale=rationale or f"{title} gap.",
        missing_evidence=[f"skill:{title.lower()}"],
    )


def _uncertainty(severity: str, title: str, rationale: str = "") -> UncertaintyItem:
    return UncertaintyItem(
        category="gap",
        title=title,
        severity=severity,
        rationale=rationale or f"{title} uncertainty.",
        related_entities=[f"skill:{title.lower()}"],
        evidence_count=1,
    )


def _confidence(overall: float) -> ConfidenceResult:
    return ConfidenceResult(
        overall_confidence=overall,
        claim_confidence=overall,
        evidence_confidence=overall,
        uncertainty_penalty=1.0 - overall,
        explanation="Test confidence explanation.",
    )


def _result(
    *,
    claims: list[ReasoningClaim] | None = None,
    gaps: GapAnalysis | None = None,
    uncertainties: UncertaintyAnalysis | None = None,
    confidence: float = 0.85,
    summary: ReasoningSummary | None = None,
) -> ReasoningResult:
    return ReasoningResult(
        claims=claims or [_claim("a"), _claim("b")],
        gaps=gaps or GapAnalysis(),
        uncertainties=uncertainties or UncertaintyAnalysis(),
        confidence=_confidence(confidence),
        summary=summary or ReasoningSummary(),
    )


def test_strong_hire_recommendation(engine: DecisionEngine) -> None:
    result = engine.decide(
        _result(confidence=0.92, claims=[_claim("a"), _claim("b")])
    )
    assert result.recommendation == Recommendation.STRONG_HIRE
    assert result.next_step == "Proceed to final interview."


def test_hire_recommendation(engine: DecisionEngine) -> None:
    result = engine.decide(_result(confidence=0.85))
    assert result.recommendation == Recommendation.HIRE
    assert result.next_step == "Proceed to technical interview."


def test_interview_recommendation(engine: DecisionEngine) -> None:
    result = engine.decide(_result(confidence=0.72))
    assert result.recommendation == Recommendation.INTERVIEW
    assert result.next_step == "Schedule technical interview."


def test_interview_with_review_recommendation(engine: DecisionEngine) -> None:
    result = engine.decide(_result(confidence=0.58))
    assert result.recommendation == Recommendation.INTERVIEW_WITH_REVIEW
    assert result.next_step == "Recruiter review recommended."


def test_needs_more_information_low_confidence(engine: DecisionEngine) -> None:
    result = engine.decide(_result(confidence=0.42))
    assert result.recommendation == Recommendation.NEEDS_MORE_INFORMATION
    assert result.next_step == "Collect additional evidence."


def test_needs_more_information_multiple_moderate_gaps(engine: DecisionEngine) -> None:
    gaps = GapAnalysis(
        moderate=[_gap("moderate", "AWS"), _gap("moderate", "Kubernetes")]
    )
    result = engine.decide(_result(confidence=0.88, gaps=gaps))
    assert result.recommendation == Recommendation.NEEDS_MORE_INFORMATION


def test_reject_low_confidence(engine: DecisionEngine) -> None:
    result = engine.decide(_result(confidence=0.30, claims=[]))
    assert result.recommendation == Recommendation.REJECT
    assert result.next_step == "Do not proceed."


def test_reject_multiple_critical_gaps(engine: DecisionEngine) -> None:
    gaps = GapAnalysis(
        critical=[_gap("critical", "Python"), _gap("critical", "AWS")]
    )
    result = engine.decide(_result(confidence=0.80, gaps=gaps))
    assert result.recommendation == Recommendation.REJECT


def test_critical_gap_blocks_hire(engine: DecisionEngine) -> None:
    gaps = GapAnalysis(critical=[_gap("critical", "AWS", "AWS production experience missing.")])
    result = engine.decide(_result(confidence=0.88, gaps=gaps))
    assert result.recommendation == Recommendation.INTERVIEW


def test_high_uncertainty_blocks_strong_hire(engine: DecisionEngine) -> None:
    uncertainties = UncertaintyAnalysis(
        high=[_uncertainty("high", "Leadership", "Leadership evidence is contradictory.")]
    )
    result = engine.decide(_result(confidence=0.92, uncertainties=uncertainties))
    assert result.recommendation == Recommendation.HIRE


def test_medium_uncertainty_does_not_block_hire(engine: DecisionEngine) -> None:
    uncertainties = UncertaintyAnalysis(
        medium=[_uncertainty("medium", "Sparse", "Sparse evidence.")]
    )
    result = engine.decide(_result(confidence=0.86, uncertainties=uncertainties))
    assert result.recommendation == Recommendation.HIRE


def test_empty_reasoning_result(engine: DecisionEngine) -> None:
    empty = ReasoningResult(
        claims=[],
        gaps=GapAnalysis(),
        uncertainties=UncertaintyAnalysis(),
        confidence=_confidence(0.25),
        summary=ReasoningSummary(),
    )
    result = engine.decide(empty)
    assert result.recommendation == Recommendation.REJECT
    assert "No synthesized reasoning claims" in result.rationale[0]


def test_deterministic_recommendation(engine: DecisionEngine) -> None:
    payload = _result(confidence=0.74, gaps=GapAnalysis(moderate=[_gap("moderate", "Cloud")]))
    assert engine.decide(payload) == engine.decide(payload)


def test_rationale_from_existing_outputs(engine: DecisionEngine) -> None:
    gaps = GapAnalysis(moderate=[_gap("moderate", "Cloud", "Moderate cloud experience gap detected.")])
    result = engine.decide(_result(confidence=0.58, gaps=gaps))
    assert any("cloud" in line.lower() for line in result.rationale)
    assert len(result.rationale) <= 5


def test_blockers_from_critical_gaps(engine: DecisionEngine) -> None:
    gaps = GapAnalysis(
        critical=[_gap("critical", "AWS", "AWS production experience missing")]
    )
    result = engine.decide(_result(confidence=0.70, gaps=gaps))
    assert "AWS production experience missing" in result.blockers


def test_blockers_from_high_uncertainty(engine: DecisionEngine) -> None:
    uncertainties = UncertaintyAnalysis(
        high=[_uncertainty("high", "Leadership", "Leadership evidence is contradictory.")]
    )
    result = engine.decide(_result(confidence=0.70, uncertainties=uncertainties))
    assert "Leadership evidence is contradictory." in result.blockers


def test_blockers_limited_to_five(engine: DecisionEngine) -> None:
    gaps = GapAnalysis(
        critical=[_gap("critical", f"G{i}", f"Blocker {i}") for i in range(8)]
    )
    result = engine.decide(_result(confidence=0.20, gaps=gaps))
    assert len(result.blockers) == 5


def test_duplicate_blockers_removed(engine: DecisionEngine) -> None:
    gaps = GapAnalysis(
        critical=[
            _gap("critical", "AWS", "AWS production experience missing"),
            _gap("critical", "AWS2", "AWS production experience missing"),
        ]
    )
    result = engine.decide(_result(confidence=0.20, gaps=gaps))
    assert result.blockers.count("AWS production experience missing") == 1


def test_boundary_confidence_strong_hire(engine: DecisionEngine) -> None:
    assert (
        engine.decide(_result(confidence=0.90)).recommendation
        == Recommendation.STRONG_HIRE
    )


def test_boundary_confidence_hire(engine: DecisionEngine) -> None:
    assert engine.decide(_result(confidence=0.80)).recommendation == Recommendation.HIRE


def test_boundary_confidence_interview(engine: DecisionEngine) -> None:
    assert engine.decide(_result(confidence=0.65)).recommendation == Recommendation.INTERVIEW


def test_boundary_confidence_interview_with_review(engine: DecisionEngine) -> None:
    assert (
        engine.decide(_result(confidence=0.50)).recommendation
        == Recommendation.INTERVIEW_WITH_REVIEW
    )


def test_boundary_confidence_needs_more_information(engine: DecisionEngine) -> None:
    assert (
        engine.decide(_result(confidence=0.35)).recommendation
        == Recommendation.NEEDS_MORE_INFORMATION
    )


def test_score_clamped_to_unit_interval(engine: DecisionEngine) -> None:
    result = engine.decide(_result(confidence=0.99))
    assert 0.0 <= result.score <= 1.0


def test_reject_score_capped(engine: DecisionEngine) -> None:
    result = engine.decide(_result(confidence=0.10, claims=[]))
    assert result.score <= 0.34


def test_inputs_not_mutated(engine: DecisionEngine) -> None:
    payload = _result(
        confidence=0.82,
        gaps=GapAnalysis(moderate=[_gap("moderate", "Cloud")]),
    )
    before = copy.deepcopy(payload)
    engine.decide(payload)
    assert payload == before


def test_invalid_input_type_raises(engine: DecisionEngine) -> None:
    with pytest.raises(TypeError, match="ReasoningResult"):
        engine.decide("not-a-result")  # type: ignore[arg-type]


def test_decision_result_fields(engine: DecisionEngine) -> None:
    result = engine.decide(_result(confidence=0.85))
    assert isinstance(result, DecisionResult)
    assert result.rationale
    assert isinstance(result.blockers, list)
    assert result.next_step


def test_mock_fixture_end_to_end_decision() -> None:
    reasoning = ReasoningEngine().reason(load_graph(), load_role_dna())
    decision = DecisionEngine().decide(reasoning)
    assert decision.recommendation in Recommendation
    assert 0.0 <= decision.score <= 1.0
    assert decision.next_step


def test_rationale_mentions_high_confidence(engine: DecisionEngine) -> None:
    result = engine.decide(_result(confidence=0.91))
    assert any("confidence" in line.lower() for line in result.rationale)


def test_no_blockers_when_clean_reasoning(engine: DecisionEngine) -> None:
    result = engine.decide(_result(confidence=0.91))
    assert result.blockers == []


def test_summary_strengths_can_appear_in_rationale(engine: DecisionEngine) -> None:
    summary = ReasoningSummary(strengths=["Strong Python across sources."])
    result = engine.decide(_result(confidence=0.58, summary=summary))
    assert any("Strong Python" in line for line in result.rationale)
