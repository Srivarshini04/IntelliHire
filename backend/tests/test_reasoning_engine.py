"""Unit tests — ReasoningEngine orchestration."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from app.intelligence.reasoning.types import MaterialityMap
from app.mock import load_graph, load_role_dna
from app.intelligence.reasoning.confidence_engine import ConfidenceEngine, ConfidenceResult
from app.intelligence.reasoning.gap_analyzer import GapAnalysis, GapAnalyzer, GapItem
from app.intelligence.reasoning.reasoning_engine import ReasoningEngine, ReasoningResult
from app.intelligence.reasoning.summary_composer import ReasoningSummary, SummaryComposer
from app.intelligence.reasoning.uncertainty_detector import UncertaintyAnalysis, UncertaintyDetector
from app.shared.enums import Intensity
from app.shared.models import CandidateGraph, ReasoningClaim, RoleDNA


@pytest.fixture
def engine() -> ReasoningEngine:
    return ReasoningEngine()


def _role(
    must_have: list[str] | None = None,
    nice_to_have: list[str] | None = None,
) -> RoleDNA:
    return RoleDNA(
        role_dna_id="roledna:test",
        job_id="JOB_TEST",
        role_summary="Test role",
        must_have_skills=must_have or [],
        nice_to_have_skills=nice_to_have or [],
    )


def _empty_graph() -> CandidateGraph:
    return CandidateGraph(
        graph_id="graph:empty",
        candidate_id="CAND_EMPTY",
        job_id="JOB_TEST",
        nodes=[],
        edges=[],
        evidence_ledger=[],
    )


class _RecordingClaimSynthesizer:
    def __init__(self, order: list[str], claims: list[ReasoningClaim]) -> None:
        self._order = order
        self._claims = claims

    def synthesize(
        self,
        graph: CandidateGraph,
        materiality: MaterialityMap,
        role: RoleDNA,
    ) -> list[ReasoningClaim]:
        self._order.append("claims")
        return list(self._claims)


class _RecordingGapAnalyzer:
    def __init__(self, order: list[str], gaps: GapAnalysis) -> None:
        self._order = order
        self._gaps = gaps

    def analyze(
        self,
        graph: CandidateGraph,
        role: RoleDNA,
        claims: list[ReasoningClaim],
    ) -> GapAnalysis:
        self._order.append("gaps")
        return self._gaps


class _RecordingUncertaintyDetector:
    def __init__(self, order: list[str], uncertainties: UncertaintyAnalysis) -> None:
        self._order = order
        self._uncertainties = uncertainties

    def detect(
        self,
        graph: CandidateGraph,
        role: RoleDNA,
        claims: list[ReasoningClaim],
        gaps: GapAnalysis,
    ) -> UncertaintyAnalysis:
        self._order.append("uncertainties")
        return self._uncertainties


class _RecordingConfidenceEngine:
    def __init__(self, order: list[str], confidence: ConfidenceResult) -> None:
        self._order = order
        self._confidence = confidence

    def compute(
        self,
        claims: list[ReasoningClaim],
        gaps: GapAnalysis,
        uncertainties: UncertaintyAnalysis,
    ) -> ConfidenceResult:
        self._order.append("confidence")
        return self._confidence


class _RecordingSummaryComposer:
    def __init__(self, order: list[str], summary: ReasoningSummary) -> None:
        self._order = order
        self._summary = summary

    def compose(
        self,
        claims: list[ReasoningClaim],
        gaps: GapAnalysis,
        uncertainties: UncertaintyAnalysis,
        confidence: ConfidenceResult,
    ) -> ReasoningSummary:
        self._order.append("summary")
        return self._summary


def test_normal_pipeline_with_mock_fixtures(engine: ReasoningEngine) -> None:
    graph = load_graph()
    role = load_role_dna()
    result = engine.reason(graph, role)

    assert isinstance(result, ReasoningResult)
    assert len(result.claims) > 0
    assert result.gaps.total_count() >= 0
    assert result.uncertainties.total_count() >= 0
    assert 0.0 <= result.confidence.overall_confidence <= 1.0
    assert result.summary.overall_summary


def test_empty_graph_returns_empty_claims(engine: ReasoningEngine) -> None:
    result = engine.reason(_empty_graph(), _role())
    assert result.claims == []
    assert isinstance(result.gaps, GapAnalysis)
    assert isinstance(result.uncertainties, UncertaintyAnalysis)
    assert isinstance(result.confidence, ConfidenceResult)
    assert isinstance(result.summary, ReasoningSummary)


def test_empty_role_still_runs_pipeline(engine: ReasoningEngine) -> None:
    graph = load_graph()
    role = RoleDNA(
        role_dna_id="roledna:empty",
        job_id="JOB_EMPTY",
        role_summary="Empty role",
    )
    result = engine.reason(graph, role)
    assert isinstance(result, ReasoningResult)


def test_deterministic_output(engine: ReasoningEngine) -> None:
    graph = load_graph()
    role = load_role_dna()
    first = engine.reason(graph, role)
    second = engine.reason(graph, role)
    assert first == second


def test_module_invocation_order() -> None:
    order: list[str] = []
    claims = [
        ReasoningClaim(
            claim_id="c1",
            statement="s",
            entity_refs=["skill:python"],
            supporting_evidence_ids=["ev_1"],
            confidence=0.9,
            conclusion="c",
        )
    ]
    gaps = GapAnalysis()
    uncertainties = UncertaintyAnalysis()
    confidence = ConfidenceResult(
        overall_confidence=0.8,
        claim_confidence=0.8,
        evidence_confidence=0.7,
        uncertainty_penalty=0.1,
        explanation="ok",
    )
    summary = ReasoningSummary(confidence_text="conf", overall_summary="overall")

    engine = ReasoningEngine(
        claim_synthesizer=_RecordingClaimSynthesizer(order, claims),
        gap_analyzer=_RecordingGapAnalyzer(order, gaps),
        uncertainty_detector=_RecordingUncertaintyDetector(order, uncertainties),
        confidence_engine=_RecordingConfidenceEngine(order, confidence),
        summary_composer=_RecordingSummaryComposer(order, summary),
    )
    engine.reason(_empty_graph(), _role())

    assert order == ["claims", "gaps", "uncertainties", "confidence", "summary"]


def test_inputs_not_mutated(engine: ReasoningEngine) -> None:
    graph = load_graph()
    role = load_role_dna()
    graph_before = graph.model_dump()
    role_before = role.model_dump()

    engine.reason(graph, role)

    assert graph.model_dump() == graph_before
    assert role.model_dump() == role_before


def test_output_wires_claims_to_downstream_stages() -> None:
    claims = [
        ReasoningClaim(
            claim_id="claim_python",
            statement="Python",
            entity_refs=["skill:python"],
            supporting_evidence_ids=["ev_1"],
            confidence=0.9,
            materiality=Intensity.CRITICAL,
            conclusion="Strong Python.",
        )
    ]
    captured: dict[str, Any] = {}

    class _CapturingGapAnalyzer(GapAnalyzer):
        def analyze(self, graph, role, received_claims):
            captured["claims"] = received_claims
            return GapAnalysis()

    class _CapturingUncertaintyDetector(UncertaintyDetector):
        def detect(self, graph, role, received_claims, gaps):
            captured["claims_for_uncertainty"] = received_claims
            return UncertaintyAnalysis()

    engine = ReasoningEngine(
        claim_synthesizer=_RecordingClaimSynthesizer([], claims),
        gap_analyzer=_CapturingGapAnalyzer(),
        uncertainty_detector=_CapturingUncertaintyDetector(),
    )
    result = engine.reason(_empty_graph(), _role(must_have=["skill:python"]))

    assert captured["claims"] == claims
    assert captured["claims_for_uncertainty"] == claims
    assert result.claims == claims


def test_output_wires_gaps_to_confidence_and_summary() -> None:
    gaps = GapAnalysis(critical=[GapItem("must_have", "Python", "critical", "missing", [])])
    captured: dict[str, Any] = {}

    class _CapturingConfidence(ConfidenceEngine):
        def compute(self, claims, received_gaps, uncertainties):
            captured["gaps"] = received_gaps
            return super().compute(claims, received_gaps, uncertainties)

    class _CapturingSummary(SummaryComposer):
        def compose(self, claims, received_gaps, uncertainties, confidence):
            captured["gaps_for_summary"] = received_gaps
            return super().compose(claims, received_gaps, uncertainties, confidence)

    engine = ReasoningEngine(
        claim_synthesizer=_RecordingClaimSynthesizer([], []),
        gap_analyzer=_RecordingGapAnalyzer([], gaps),
        uncertainty_detector=_RecordingUncertaintyDetector([], UncertaintyAnalysis()),
        confidence_engine=_CapturingConfidence(),
        summary_composer=_CapturingSummary(),
    )
    result = engine.reason(_empty_graph(), _role())

    assert captured["gaps"] == gaps
    assert captured["gaps_for_summary"] == gaps
    assert result.gaps == gaps


def test_missing_candidate_id_raises(engine: ReasoningEngine) -> None:
    graph = CandidateGraph(
        graph_id="graph:x",
        candidate_id="",
        job_id="JOB_TEST",
        nodes=[],
        edges=[],
        evidence_ledger=[],
    )
    with pytest.raises(ValueError, match="candidate_id"):
        engine.reason(graph, _role())


def test_missing_job_id_raises(engine: ReasoningEngine) -> None:
    role = RoleDNA(role_dna_id="roledna:x", job_id="", role_summary="x")
    with pytest.raises(ValueError, match="job_id"):
        engine.reason(_empty_graph(), role)


def test_invalid_graph_type_raises(engine: ReasoningEngine) -> None:
    with pytest.raises(TypeError, match="CandidateGraph"):
        engine.reason("not-a-graph", _role())  # type: ignore[arg-type]


def test_invalid_role_type_raises(engine: ReasoningEngine) -> None:
    with pytest.raises(TypeError, match="RoleDNA"):
        engine.reason(_empty_graph(), "not-a-role")  # type: ignore[arg-type]


def test_reasoning_result_fields_present(engine: ReasoningEngine) -> None:
    result = engine.reason(load_graph(), load_role_dna())
    assert hasattr(result, "claims")
    assert hasattr(result, "gaps")
    assert hasattr(result, "uncertainties")
    assert hasattr(result, "confidence")
    assert hasattr(result, "summary")


def test_empty_graph_confidence_is_deterministic(engine: ReasoningEngine) -> None:
    first = engine.reason(_empty_graph(), _role())
    second = engine.reason(_empty_graph(), _role())
    assert first.confidence == second.confidence
    assert first.confidence.overall_confidence < 0.8


def test_empty_graph_summary_uses_confidence_only(engine: ReasoningEngine) -> None:
    result = engine.reason(_empty_graph(), _role())
    assert result.summary.strengths == []
    assert result.summary.overall_summary == result.summary.confidence_text


def test_dependency_injection_uses_provided_modules() -> None:
    custom_summary = ReasoningSummary(
        strengths=["Custom strength."],
        confidence_text="Custom confidence.",
        overall_summary="Custom overall.",
    )
    engine = ReasoningEngine(
        claim_synthesizer=_RecordingClaimSynthesizer([], []),
        gap_analyzer=_RecordingGapAnalyzer([], GapAnalysis()),
        uncertainty_detector=_RecordingUncertaintyDetector([], UncertaintyAnalysis()),
        confidence_engine=_RecordingConfidenceEngine(
            [],
            ConfidenceResult(0.5, 0.0, 0.0, 0.5, "custom"),
        ),
        summary_composer=_RecordingSummaryComposer([], custom_summary),
    )
    result = engine.reason(_empty_graph(), _role())
    assert result.summary == custom_summary


def test_copy_graph_produces_same_result(engine: ReasoningEngine) -> None:
    graph = load_graph()
    role = load_role_dna()
    baseline = engine.reason(graph, role)
    cloned = CandidateGraph.model_validate(copy.deepcopy(graph.model_dump()))
    assert engine.reason(cloned, role) == baseline


def test_uncertainties_receive_gap_output() -> None:
    gaps = GapAnalysis(moderate=[GapItem("must_have", "Vector", "moderate", "gap", [])])
    captured: dict[str, GapAnalysis] = {}

    class _CapturingUncertainty(UncertaintyDetector):
        def detect(self, graph, role, claims, received_gaps):
            captured["gaps"] = received_gaps
            return UncertaintyAnalysis()

    engine = ReasoningEngine(
        claim_synthesizer=_RecordingClaimSynthesizer([], []),
        gap_analyzer=_RecordingGapAnalyzer([], gaps),
        uncertainty_detector=_CapturingUncertainty(),
    )
    engine.reason(_empty_graph(), _role())

    assert captured["gaps"] == gaps


def test_summary_receives_confidence_output() -> None:
    confidence = ConfidenceResult(0.77, 0.7, 0.65, 0.12, "wired")
    captured: dict[str, ConfidenceResult] = {}

    class _CapturingSummary(SummaryComposer):
        def compose(self, claims, gaps, uncertainties, received_confidence):
            captured["confidence"] = received_confidence
            return super().compose(claims, gaps, uncertainties, received_confidence)

    engine = ReasoningEngine(
        claim_synthesizer=_RecordingClaimSynthesizer([], []),
        gap_analyzer=_RecordingGapAnalyzer([], GapAnalysis()),
        uncertainty_detector=_RecordingUncertaintyDetector([], UncertaintyAnalysis()),
        confidence_engine=_RecordingConfidenceEngine([], confidence),
        summary_composer=_CapturingSummary(),
    )
    result = engine.reason(_empty_graph(), _role())
    assert captured["confidence"] == confidence
    assert result.confidence == confidence


def test_mock_fixture_has_expected_claim_ids(engine: ReasoningEngine) -> None:
    result = engine.reason(load_graph(), load_role_dna())
    claim_ids = {claim.claim_id for claim in result.claims}
    assert "claim_python" in claim_ids
    assert "claim_retrieval" in claim_ids


def test_reasoning_engine_default_constructible() -> None:
    engine = ReasoningEngine()
    assert engine is not None


def test_empty_role_with_empty_graph_zero_claims(engine: ReasoningEngine) -> None:
    role = RoleDNA(role_dna_id="roledna:e", job_id="JOB_E", role_summary="empty")
    result = engine.reason(_empty_graph(), role)
    assert result.claims == []
    assert result.gaps.total_count() == 0
