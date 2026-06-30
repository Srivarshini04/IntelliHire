"""Unit tests — ConfidenceEngine (deterministic reasoning confidence)."""

from __future__ import annotations

import copy

import pytest

from app.intelligence.reasoning.claim_synthesizer import ClaimSynthesizer
from app.intelligence.reasoning.types import MaterialityMap
from app.mock import load_graph, load_role_dna
from app.intelligence.reasoning.confidence_engine import ConfidenceEngine, ConfidenceResult
from app.intelligence.reasoning.gap_analyzer import GapAnalysis, GapAnalyzer, GapItem
from app.intelligence.reasoning.uncertainty_detector import UncertaintyAnalysis, UncertaintyItem
from app.shared.enums import Intensity
from app.shared.models import ReasoningClaim


@pytest.fixture
def engine() -> ConfidenceEngine:
    return ConfidenceEngine()


def _claim(
    claim_id: str,
    *,
    confidence: float = 0.85,
    supporting: list[str] | None = None,
    counter: list[str] | None = None,
    materiality: Intensity = Intensity.HIGH,
) -> ReasoningClaim:
    return ReasoningClaim(
        claim_id=claim_id,
        statement=f"Statement for {claim_id}",
        entity_refs=[f"skill:{claim_id}"],
        supporting_evidence_ids=supporting or ["ev_1"],
        counter_evidence_ids=counter or [],
        confidence=confidence,
        materiality=materiality,
        conclusion="Conclusion",
    )


def _gap(severity: str, title: str = "Gap") -> GapItem:
    return GapItem(
        category="must_have",
        title=title,
        severity=severity,
        rationale="Test gap",
        missing_evidence=[f"skill:{title.lower()}"],
    )


def _uncertainty(severity: str, title: str = "Uncertainty") -> UncertaintyItem:
    return UncertaintyItem(
        category="gap",
        title=title,
        severity=severity,
        rationale="Test uncertainty",
        related_entities=[f"skill:{title.lower()}"],
        evidence_count=1,
    )


def test_no_claims_reduces_confidence(engine: ConfidenceEngine) -> None:
    result = engine.compute([], GapAnalysis(), UncertaintyAnalysis())
    assert result.claim_confidence == 0.0
    assert result.evidence_confidence == 0.0
    assert result.overall_confidence < 0.8


def test_many_strong_claims_increase_confidence(engine: ConfidenceEngine) -> None:
    weak = engine.compute(
        [_claim("a", confidence=0.6)],
        GapAnalysis(),
        UncertaintyAnalysis(),
    )
    strong = engine.compute(
        [
            _claim("a", confidence=0.9, supporting=["ev_a", "ev_b"]),
            _claim("b", confidence=0.88, supporting=["ev_c", "ev_d"]),
            _claim("c", confidence=0.92, supporting=["ev_e", "ev_f"]),
        ],
        GapAnalysis(),
        UncertaintyAnalysis(),
    )
    assert strong.overall_confidence > weak.overall_confidence
    assert strong.claim_confidence > weak.claim_confidence


def test_critical_gaps_reduce_confidence(engine: ConfidenceEngine) -> None:
    claims = [_claim("a", confidence=0.9)]
    baseline = engine.compute(claims, GapAnalysis(), UncertaintyAnalysis())
    penalized = engine.compute(
        claims,
        GapAnalysis(critical=[_gap("critical", "Python"), _gap("critical", "Fastapi")]),
        UncertaintyAnalysis(),
    )
    assert penalized.overall_confidence < baseline.overall_confidence
    assert penalized.uncertainty_penalty > baseline.uncertainty_penalty


def test_moderate_gaps_reduce_confidence(engine: ConfidenceEngine) -> None:
    claims = [_claim("a", confidence=0.9)]
    baseline = engine.compute(claims, GapAnalysis(), UncertaintyAnalysis())
    penalized = engine.compute(
        claims,
        GapAnalysis(moderate=[_gap("moderate", "Eval")]),
        UncertaintyAnalysis(),
    )
    assert penalized.overall_confidence < baseline.overall_confidence


def test_minor_gaps_small_penalty(engine: ConfidenceEngine) -> None:
    claims = [_claim("a", confidence=0.9)]
    moderate = engine.compute(
        claims,
        GapAnalysis(moderate=[_gap("moderate", "Eval")]),
        UncertaintyAnalysis(),
    )
    minor = engine.compute(
        claims,
        GapAnalysis(minor=[_gap("minor", "K8s")]),
        UncertaintyAnalysis(),
    )
    assert minor.overall_confidence > moderate.overall_confidence


def test_high_uncertainty_penalty(engine: ConfidenceEngine) -> None:
    claims = [_claim("a", confidence=0.9)]
    baseline = engine.compute(claims, GapAnalysis(), UncertaintyAnalysis())
    penalized = engine.compute(
        claims,
        GapAnalysis(),
        UncertaintyAnalysis(high=[_uncertainty("high", "Conflict")]),
    )
    assert penalized.overall_confidence < baseline.overall_confidence


def test_medium_uncertainty_penalty(engine: ConfidenceEngine) -> None:
    claims = [_claim("a", confidence=0.9)]
    baseline = engine.compute(claims, GapAnalysis(), UncertaintyAnalysis())
    penalized = engine.compute(
        claims,
        GapAnalysis(),
        UncertaintyAnalysis(medium=[_uncertainty("medium", "Sparse")]),
    )
    assert penalized.overall_confidence < baseline.overall_confidence


def test_low_uncertainty_small_penalty(engine: ConfidenceEngine) -> None:
    claims = [_claim("a", confidence=0.9)]
    medium = engine.compute(
        claims,
        GapAnalysis(),
        UncertaintyAnalysis(medium=[_uncertainty("medium", "Sparse")]),
    )
    low = engine.compute(
        claims,
        GapAnalysis(),
        UncertaintyAnalysis(low=[_uncertainty("low", "Optional")]),
    )
    assert low.overall_confidence > medium.overall_confidence


def test_score_clamped_to_unit_interval(engine: ConfidenceEngine) -> None:
    claims = [_claim("a", confidence=0.99, supporting=["ev_a", "ev_b", "ev_c"])]
    gaps = GapAnalysis(
        critical=[_gap("critical", f"g{i}") for i in range(10)],
    )
    uncertainties = UncertaintyAnalysis(
        high=[_uncertainty("high", f"u{i}") for i in range(10)],
    )
    result = engine.compute(claims, gaps, uncertainties)
    assert 0.0 <= result.overall_confidence <= 1.0
    assert 0.0 <= result.claim_confidence <= 1.0
    assert 0.0 <= result.evidence_confidence <= 1.0


def test_deterministic_output(engine: ConfidenceEngine) -> None:
    claims = [_claim("a"), _claim("b", confidence=0.8)]
    gaps = GapAnalysis(moderate=[_gap("moderate", "Eval")])
    uncertainties = UncertaintyAnalysis(low=[_uncertainty("low", "Nice")])
    first = engine.compute(claims, gaps, uncertainties)
    second = engine.compute(claims, gaps, uncertainties)
    assert first == second


def test_inputs_not_mutated(engine: ConfidenceEngine) -> None:
    claims = [_claim("a")]
    gaps = GapAnalysis(minor=[_gap("minor", "K8s")])
    uncertainties = UncertaintyAnalysis(medium=[_uncertainty("medium", "Sparse")])

    claims_before = [c.model_dump() for c in claims]
    gaps_before = copy.deepcopy(gaps)
    uncertainties_before = copy.deepcopy(uncertainties)

    engine.compute(claims, gaps, uncertainties)

    assert [c.model_dump() for c in claims] == claims_before
    assert gaps == gaps_before
    assert uncertainties == uncertainties_before


def test_explanation_is_non_empty_and_includes_score(engine: ConfidenceEngine) -> None:
    result = engine.compute([_claim("a")], GapAnalysis(), UncertaintyAnalysis())
    assert result.explanation.strip()
    assert f"{result.overall_confidence:.2f}" in result.explanation


def test_explanation_mentions_counts(engine: ConfidenceEngine) -> None:
    claims = [_claim("a"), _claim("b")]
    gaps = GapAnalysis(critical=[_gap("critical", "Python")])
    uncertainties = UncertaintyAnalysis(high=[_uncertainty("high", "Conflict")])
    result = engine.compute(claims, gaps, uncertainties)
    assert "2 claim" in result.explanation
    assert "1 gap" in result.explanation
    assert "1 uncertainty" in result.explanation


def test_claim_confidence_zero_without_supporting_evidence(engine: ConfidenceEngine) -> None:
    claims = [
        ReasoningClaim(
            claim_id="c1",
            statement="s",
            entity_refs=["skill:x"],
            supporting_evidence_ids=[],
            counter_evidence_ids=["ev_c"],
            confidence=0.9,
            conclusion="c",
        )
    ]
    result = engine.compute(claims, GapAnalysis(), UncertaintyAnalysis())
    assert result.claim_confidence == 0.0


def test_evidence_confidence_higher_with_more_support(engine: ConfidenceEngine) -> None:
    single = engine.compute([_claim("a", supporting=["ev_1"])], GapAnalysis(), UncertaintyAnalysis())
    multi = engine.compute(
        [_claim("a", supporting=["ev_1", "ev_2", "ev_3"])],
        GapAnalysis(),
        UncertaintyAnalysis(),
    )
    assert multi.evidence_confidence >= single.evidence_confidence


def test_counter_evidence_reduces_evidence_confidence(engine: ConfidenceEngine) -> None:
    clean = engine.compute([_claim("a", supporting=["ev_1"])], GapAnalysis(), UncertaintyAnalysis())
    conflict = engine.compute(
        [_claim("a", supporting=["ev_1"], counter=["ev_c"])],
        GapAnalysis(),
        UncertaintyAnalysis(),
    )
    assert conflict.evidence_confidence < clean.evidence_confidence


def test_uncertainty_penalty_sums_gap_and_uncertainty(engine: ConfidenceEngine) -> None:
    gaps = GapAnalysis(critical=[_gap("critical", "Python")])
    uncertainties = UncertaintyAnalysis(high=[_uncertainty("high", "Conflict")])
    result = engine.compute([_claim("a")], gaps, uncertainties)
    assert result.uncertainty_penalty > 0.15


def test_few_claims_penalized_vs_many(engine: ConfidenceEngine) -> None:
    one = engine.compute([_claim("a")], GapAnalysis(), UncertaintyAnalysis())
    many = engine.compute(
        [_claim(f"c{i}", confidence=0.85) for i in range(5)],
        GapAnalysis(),
        UncertaintyAnalysis(),
    )
    assert many.overall_confidence > one.overall_confidence


def test_result_is_frozen_dataclass(engine: ConfidenceEngine) -> None:
    result = engine.compute([_claim("a")], GapAnalysis(), UncertaintyAnalysis())
    assert isinstance(result, ConfidenceResult)


def test_materiality_weights_affect_claim_confidence(engine: ConfidenceEngine) -> None:
    low_mat = engine.compute(
        [_claim("a", materiality=Intensity.LOW, confidence=0.9)],
        GapAnalysis(),
        UncertaintyAnalysis(),
    )
    critical_mat = engine.compute(
        [_claim("a", materiality=Intensity.CRITICAL, confidence=0.9)],
        GapAnalysis(),
        UncertaintyAnalysis(),
    )
    assert critical_mat.claim_confidence >= low_mat.claim_confidence


def test_empty_gaps_and_uncertainties_with_strong_claims(engine: ConfidenceEngine) -> None:
    claims = [
        _claim("a", confidence=0.92, supporting=["ev_a", "ev_b"]),
        _claim("b", confidence=0.9, supporting=["ev_c", "ev_d"]),
    ]
    result = engine.compute(claims, GapAnalysis(), UncertaintyAnalysis())
    assert result.overall_confidence >= 0.85


def test_mock_fixture_pipeline_confidence(
    engine: ConfidenceEngine,
) -> None:
    graph = load_graph()
    role = load_role_dna()
    claims = ClaimSynthesizer().synthesize(graph, MaterialityMap(), role)
    gaps = GapAnalyzer().analyze(graph, role, claims)
    from app.intelligence.reasoning.uncertainty_detector import UncertaintyDetector

    uncertainties = UncertaintyDetector().detect(graph, role, claims, gaps)
    result = engine.compute(claims, gaps, uncertainties)
    assert 0.0 < result.overall_confidence < 1.0
    assert result.claim_confidence > 0.0
    assert result.evidence_confidence > 0.0
    assert result.uncertainty_penalty > 0.0


def test_combined_penalties_lower_than_single_factor(engine: ConfidenceEngine) -> None:
    claims = [_claim("a", confidence=0.85)]
    gaps_only = engine.compute(
        claims,
        GapAnalysis(critical=[_gap("critical", "Python")]),
        UncertaintyAnalysis(),
    )
    uncertainties_only = engine.compute(
        claims,
        GapAnalysis(),
        UncertaintyAnalysis(high=[_uncertainty("high", "Conflict")]),
    )
    combined = engine.compute(
        claims,
        GapAnalysis(critical=[_gap("critical", "Python")]),
        UncertaintyAnalysis(high=[_uncertainty("high", "Conflict")]),
    )
    assert combined.overall_confidence < gaps_only.overall_confidence
    assert combined.overall_confidence < uncertainties_only.overall_confidence


def test_overall_confidence_rounded_to_four_decimals(engine: ConfidenceEngine) -> None:
    result = engine.compute([_claim("a")], GapAnalysis(), UncertaintyAnalysis())
    text = f"{result.overall_confidence:.4f}"
    assert result.overall_confidence == float(text)


def test_strong_claim_count_reflected_in_explanation(engine: ConfidenceEngine) -> None:
    claims = [
        _claim("a", confidence=0.9, supporting=["ev_a", "ev_b"]),
        _claim("b", confidence=0.88, supporting=["ev_c", "ev_d"]),
    ]
    result = engine.compute(claims, GapAnalysis(), UncertaintyAnalysis())
    assert "2 strong" in result.explanation


def test_no_gaps_no_uncertainties_minimal_penalty(engine: ConfidenceEngine) -> None:
    result = engine.compute(
        [_claim("a", confidence=0.9), _claim("b", confidence=0.88)],
        GapAnalysis(),
        UncertaintyAnalysis(),
    )
    assert result.uncertainty_penalty == 0.0


def test_claim_without_support_does_not_raise(engine: ConfidenceEngine) -> None:
    claims = [
        ReasoningClaim(
            claim_id="c1",
            statement="s",
            entity_refs=["skill:x"],
            supporting_evidence_ids=[],
            confidence=0.5,
            conclusion="c",
        )
    ]
    result = engine.compute(claims, GapAnalysis(), UncertaintyAnalysis())
    assert isinstance(result, ConfidenceResult)


def test_copy_produces_same_result(engine: ConfidenceEngine) -> None:
    claims = [_claim("a"), _claim("b")]
    gaps = GapAnalysis(moderate=[_gap("moderate", "Eval")])
    uncertainties = UncertaintyAnalysis(low=[_uncertainty("low", "Nice")])
    first = engine.compute(claims, gaps, uncertainties)
    second = engine.compute(
        [ReasoningClaim.model_validate(c.model_dump()) for c in claims],
        copy.deepcopy(gaps),
        copy.deepcopy(uncertainties),
    )
    assert first == second


def test_high_materiality_claims_boost_overall(engine: ConfidenceEngine) -> None:
    low = engine.compute(
        [_claim("a", confidence=0.8, materiality=Intensity.LOW)],
        GapAnalysis(),
        UncertaintyAnalysis(),
    )
    high = engine.compute(
        [_claim("a", confidence=0.8, materiality=Intensity.CRITICAL)],
        GapAnalysis(),
        UncertaintyAnalysis(),
    )
    assert high.overall_confidence >= low.overall_confidence
