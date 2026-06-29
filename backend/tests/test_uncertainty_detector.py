"""Unit tests — UncertaintyDetector (read-only epistemic uncertainty)."""

from __future__ import annotations

import copy

import pytest

from app.intelligence.reasoning.claim_synthesizer import ClaimSynthesizer
from app.intelligence.reasoning.types import MaterialityMap
from app.mock import load_graph, load_role_dna
from app.intelligence.reasoning.gap_analyzer import GapAnalysis, GapAnalyzer, GapItem
from app.intelligence.reasoning.uncertainty_detector import (
    UncertaintyAnalysis,
    UncertaintyDetector,
    UncertaintyItem,
)
from app.shared.enums import EvidencePolarity, EvidenceSource, EvidenceType, GraphNodeType
from app.shared.models import CandidateGraph, GraphNode, ReasoningClaim, RoleDNA
from app.shared.models.evidence import EvidenceLedgerEntry


@pytest.fixture
def detector() -> UncertaintyDetector:
    return UncertaintyDetector()


@pytest.fixture
def gap_analyzer() -> GapAnalyzer:
    return GapAnalyzer()


def _role(
    must_have: list[str] | None = None,
    nice_to_have: list[str] | None = None,
    domain: str | None = None,
) -> RoleDNA:
    return RoleDNA(
        role_dna_id="roledna:test",
        job_id="JOB_TEST",
        role_summary="Test role",
        must_have_skills=must_have or [],
        nice_to_have_skills=nice_to_have or [],
        domain=domain,
    )


def _graph(
    nodes: list[GraphNode] | None = None,
    ledger: list[EvidenceLedgerEntry] | None = None,
) -> CandidateGraph:
    return CandidateGraph(
        graph_id="graph:test",
        candidate_id="CAND_TEST",
        job_id="JOB_TEST",
        nodes=nodes or [],
        edges=[],
        evidence_ledger=ledger or [],
    )


def _node(
    entity_ref: str,
    *,
    confidence: float = 0.9,
    label: str | None = None,
) -> GraphNode:
    return GraphNode(
        id=entity_ref,
        type=GraphNodeType.SKILL,
        label=label or entity_ref.split(":")[-1],
        confidence=confidence,
        evidence_ids=[],
    )


def _ledger_entry(
    entity_ref: str,
    *,
    evidence_id: str = "ev_1",
    source: EvidenceSource = EvidenceSource.RESUME,
    polarity: EvidencePolarity = EvidencePolarity.SUPPORTS,
    confidence: float = 0.85,
) -> EvidenceLedgerEntry:
    return EvidenceLedgerEntry(
        evidence_id=evidence_id,
        candidate_id="CAND_TEST",
        source=source,
        evidence_type=EvidenceType.SKILL,
        entity_ref=entity_ref,
        claim=f"Evidence for {entity_ref}",
        polarity=polarity,
        confidence=confidence,
        supporting_node_id=entity_ref,
    )


def _claim(
    entity_ref: str,
    *,
    claim_id: str = "claim_1",
    supporting: list[str] | None = None,
    counter: list[str] | None = None,
    confidence: float = 0.85,
) -> ReasoningClaim:
    return ReasoningClaim(
        claim_id=claim_id,
        statement=f"Claim about {entity_ref}",
        entity_refs=[entity_ref],
        supporting_evidence_ids=supporting or [],
        counter_evidence_ids=counter or [],
        confidence=confidence,
        conclusion="Test conclusion",
    )


def _detect(
    detector: UncertaintyDetector,
    graph: CandidateGraph,
    role: RoleDNA,
    claims: list[ReasoningClaim],
    gaps: GapAnalysis | None = None,
    gap_analyzer: GapAnalyzer | None = None,
) -> UncertaintyAnalysis:
    if gaps is None:
        analyzer = gap_analyzer or GapAnalyzer()
        gaps = analyzer.analyze(graph, role, claims)
    return detector.detect(graph, role, claims, gaps)


def test_no_uncertainty_when_fully_supported(detector: UncertaintyDetector) -> None:
    role = _role(must_have=["skill:python"])
    graph = _graph(
        nodes=[_node("skill:python", confidence=0.92)],
        ledger=[
            _ledger_entry("skill:python", evidence_id="ev_a", source=EvidenceSource.RESUME),
            _ledger_entry("skill:python", evidence_id="ev_b", source=EvidenceSource.GITHUB),
        ],
    )
    claims = [_claim("skill:python", supporting=["ev_a", "ev_b"], confidence=0.9)]
    result = _detect(detector, graph, role, claims)
    assert result.total_count() == 0


def test_empty_graph_empty_role_no_uncertainty(detector: UncertaintyDetector) -> None:
    result = _detect(detector, _graph(), _role(), [])
    assert result == UncertaintyAnalysis()


def test_empty_claims_still_detects_graph_uncertainty(detector: UncertaintyDetector) -> None:
    role = _role(must_have=["skill:python"])
    result = _detect(detector, _graph(), role, [])
    assert result.total_count() >= 1
    assert result.high


def test_conflicting_evidence_high_severity(detector: UncertaintyDetector) -> None:
    role = _role(must_have=["skill:leadership"])
    graph = _graph(
        nodes=[_node("skill:leadership", confidence=0.5)],
        ledger=[
            _ledger_entry("skill:leadership", evidence_id="ev_s", confidence=0.8),
            _ledger_entry(
                "skill:leadership",
                evidence_id="ev_c",
                polarity=EvidencePolarity.CONTRADICTS,
                confidence=0.7,
            ),
        ],
    )
    result = _detect(detector, graph, role, [])
    conflict = next(item for item in result.high if item.category == "conflicting_evidence")
    assert conflict.severity == "high"
    assert "skill:leadership" in conflict.related_entities


def test_claim_level_conflict_high_severity(detector: UncertaintyDetector) -> None:
    role = _role()
    graph = _graph(nodes=[_node("skill:python")])
    claims = [_claim("skill:python", supporting=["ev_a"], counter=["ev_b"])]
    result = _detect(detector, graph, role, claims)
    assert any(item.category == "conflicting_evidence" for item in result.high)


def test_weak_evidence_medium_severity(detector: UncertaintyDetector) -> None:
    role = _role(must_have=["skill:python"])
    graph = _graph(
        nodes=[_node("skill:python", confidence=0.45)],
        ledger=[_ledger_entry("skill:python", confidence=0.45)],
    )
    result = _detect(detector, graph, role, [])
    weak = [item for item in result.all_items() if item.category == "weak_evidence"]
    assert len(weak) == 1
    assert weak[0].severity == "medium"


def test_sparse_evidence_medium_severity(detector: UncertaintyDetector) -> None:
    role = _role(must_have=["skill:python"])
    graph = _graph(
        nodes=[_node("skill:python", confidence=0.72)],
        ledger=[_ledger_entry("skill:python", confidence=0.72)],
    )
    result = _detect(detector, graph, role, [])
    sparse = [item for item in result.all_items() if item.category == "sparse_evidence"]
    assert len(sparse) == 1
    assert sparse[0].severity == "medium"


def test_missing_critical_competency_high_severity(detector: UncertaintyDetector) -> None:
    role = _role(must_have=["skill:vector_search"])
    result = _detect(detector, _graph(), role, [])
    missing = [item for item in result.high if item.category == "missing_evidence"]
    assert len(missing) == 1
    assert "skill:vector_search" in missing[0].related_entities


def test_missing_optional_competency_low_severity_via_gap(
    detector: UncertaintyDetector,
    gap_analyzer: GapAnalyzer,
) -> None:
    role = _role(nice_to_have=["skill:kubernetes"])
    gaps = gap_analyzer.analyze(_graph(), role, [])
    result = detector.detect(_graph(), role, [], gaps)
    low = [item for item in result.low if item.category == "gap"]
    assert len(low) == 1


def test_gap_critical_maps_to_high_uncertainty(
    detector: UncertaintyDetector,
    gap_analyzer: GapAnalyzer,
) -> None:
    role = _role(must_have=["skill:python"])
    gaps = gap_analyzer.analyze(_graph(), role, [])
    result = detector.detect(_graph(), role, [], gaps)
    assert any(item.severity == "high" for item in result.high)
    assert any(
        "skill:python" in item.related_entities for item in result.high
    )


def test_gap_moderate_maps_to_medium_uncertainty(
    detector: UncertaintyDetector,
) -> None:
    gap = GapItem(
        category="must_have",
        title="FastAPI",
        severity="moderate",
        rationale="Weak coverage",
        missing_evidence=["corroboration:skill:fastapi"],
    )
    gaps = GapAnalysis(moderate=[gap])
    result = detector.detect(_graph(), _role(), [], gaps)
    assert len(result.medium) == 1
    assert result.medium[0].category == "gap"


def test_multiple_uncertainty_signals_deduped(
    detector: UncertaintyDetector,
    gap_analyzer: GapAnalyzer,
) -> None:
    role = _role(must_have=["skill:python"])
    gaps = gap_analyzer.analyze(_graph(), role, [])
    result = detector.detect(_graph(), role, [], gaps)
    python_items = [
        item for item in result.all_items() if "skill:python" in item.related_entities
    ]
    assert len(python_items) == 1


def test_deterministic_ordering(detector: UncertaintyDetector) -> None:
    role = _role(must_have=["skill:zebra", "skill:alpha"], nice_to_have=["skill:beta"])
    first = _detect(detector, _graph(), role, [])
    second = _detect(detector, _graph(), role, [])
    assert first == second


def test_inputs_not_mutated(
    detector: UncertaintyDetector,
    gap_analyzer: GapAnalyzer,
) -> None:
    role = _role(must_have=["skill:python"], nice_to_have=["skill:kubernetes"])
    graph = _graph(nodes=[_node("skill:python", confidence=0.9)])
    claims = [_claim("skill:python", supporting=["ev_a"])]
    gaps = gap_analyzer.analyze(graph, role, claims)

    role_before = role.model_dump()
    graph_before = graph.model_dump()
    claims_before = [c.model_dump() for c in claims]
    gaps_before = copy.deepcopy(gaps)

    detector.detect(graph, role, claims, gaps)

    assert role.model_dump() == role_before
    assert graph.model_dump() == graph_before
    assert [c.model_dump() for c in claims] == claims_before
    assert gaps == gaps_before


def test_uncertainty_item_fields(detector: UncertaintyDetector) -> None:
    role = _role(must_have=["skill:python"])
    result = _detect(detector, _graph(), role, [])
    item = result.high[0]
    assert isinstance(item, UncertaintyItem)
    assert item.category
    assert item.title
    assert item.severity
    assert item.rationale
    assert item.related_entities
    assert item.evidence_count >= 0


def test_well_supported_claim_suppresses_weak_and_sparse(detector: UncertaintyDetector) -> None:
    role = _role(must_have=["skill:python"])
    graph = _graph(
        nodes=[_node("skill:python", confidence=0.95)],
        ledger=[
            _ledger_entry("skill:python", evidence_id="ev_a", source=EvidenceSource.RESUME),
            _ledger_entry("skill:python", evidence_id="ev_b", source=EvidenceSource.GITHUB),
        ],
    )
    claims = [_claim("skill:python", supporting=["ev_a", "ev_b"], confidence=0.9)]
    result = _detect(detector, graph, role, claims)
    assert result.total_count() == 0


def test_nice_to_have_weak_evidence_low_severity(detector: UncertaintyDetector) -> None:
    role = _role(nice_to_have=["skill:kubernetes"])
    graph = _graph(
        nodes=[_node("skill:kubernetes", confidence=0.4)],
        ledger=[_ledger_entry("skill:kubernetes", confidence=0.4)],
    )
    result = _detect(detector, graph, role, [])
    weak = [item for item in result.all_items() if item.category == "weak_evidence"]
    assert weak[0].severity == "low"


def test_evidence_count_reflects_ledger_entries(detector: UncertaintyDetector) -> None:
    role = _role(must_have=["skill:leadership"])
    graph = _graph(
        nodes=[_node("skill:leadership", confidence=0.5)],
        ledger=[
            _ledger_entry("skill:leadership", evidence_id="ev_s"),
            _ledger_entry(
                "skill:leadership",
                evidence_id="ev_c",
                polarity=EvidencePolarity.CONTRADICTS,
            ),
        ],
    )
    result = _detect(detector, graph, role, [])
    conflict = next(item for item in result.high if item.category == "conflicting_evidence")
    assert conflict.evidence_count == 2


def test_empty_gap_analysis_still_runs_other_detectors(detector: UncertaintyDetector) -> None:
    role = _role(must_have=["skill:python"])
    result = detector.detect(_graph(), role, [], GapAnalysis())
    assert result.total_count() >= 1


def test_mock_fixture_detects_finetuning_conflict(
    detector: UncertaintyDetector,
    gap_analyzer: GapAnalyzer,
) -> None:
    graph = load_graph()
    role = load_role_dna()
    claims = ClaimSynthesizer().synthesize(graph, MaterialityMap(), role)
    gaps = gap_analyzer.analyze(graph, role, claims)
    result = detector.detect(graph, role, claims, gaps)
    entities = {entity for item in result.all_items() for entity in item.related_entities}
    assert "skill:llm_finetuning" in entities or any(
        "fine" in item.title.lower() for item in result.all_items()
    )


def test_mock_fixture_vector_search_uncertainty(
    detector: UncertaintyDetector,
    gap_analyzer: GapAnalyzer,
) -> None:
    graph = load_graph()
    role = load_role_dna()
    claims = ClaimSynthesizer().synthesize(graph, MaterialityMap(), role)
    gaps = gap_analyzer.analyze(graph, role, claims)
    result = detector.detect(graph, role, claims, gaps)
    assert result.total_count() >= 2
    assert result.high


def test_mock_fixture_satisfied_skills_not_uncertain(
    detector: UncertaintyDetector,
    gap_analyzer: GapAnalyzer,
) -> None:
    graph = load_graph()
    role = load_role_dna()
    claims = ClaimSynthesizer().synthesize(graph, MaterialityMap(), role)
    gaps = gap_analyzer.analyze(graph, role, claims)
    result = detector.detect(graph, role, claims, gaps)
    uncertain_entities = {e for item in result.all_items() for e in item.related_entities}
    assert "skill:python" not in uncertain_entities
    assert "skill:fastapi" not in uncertain_entities


def test_all_items_helper(detector: UncertaintyDetector) -> None:
    role = _role(must_have=["skill:a"], nice_to_have=["skill:b"])
    result = _detect(detector, _graph(), role, [])
    assert len(result.all_items()) == result.total_count()


def test_analysis_dataclass_defaults() -> None:
    analysis = UncertaintyAnalysis()
    assert analysis.high == []
    assert analysis.medium == []
    assert analysis.low == []
    assert analysis.total_count() == 0


def test_high_bucket_sorted_deterministically(detector: UncertaintyDetector) -> None:
    role = _role(must_have=["skill:beta", "skill:alpha"])
    result = _detect(detector, _graph(), role, [])
    titles = [item.title.lower() for item in result.high]
    assert titles == sorted(titles)


def test_duplicate_gap_entries_not_duplicated_in_output(
    detector: UncertaintyDetector,
) -> None:
    gap = GapItem(
        category="must_have",
        title="Python",
        severity="critical",
        rationale="Missing",
        missing_evidence=["skill:python"],
    )
    gaps = GapAnalysis(critical=[gap])
    role = _role(must_have=["skill:python"])
    result = detector.detect(_graph(), role, [], gaps)
    python_items = [
        item for item in result.all_items() if "skill:python" in item.related_entities
    ]
    assert len(python_items) == 1


def test_rationale_is_non_empty(detector: UncertaintyDetector) -> None:
    role = _role(must_have=["skill:python"])
    result = _detect(detector, _graph(), role, [])
    assert all(item.rationale.strip() for item in result.all_items())


def test_copy_produces_same_uncertainties(detector: UncertaintyDetector) -> None:
    role = _role(must_have=["skill:python", "skill:fastapi"])
    graph = _graph(nodes=[_node("skill:python", confidence=0.95)])
    baseline = _detect(detector, graph, role, [])
    cloned = CandidateGraph.model_validate(copy.deepcopy(graph.model_dump()))
    assert _detect(detector, cloned, role, []) == baseline


def test_interaction_with_gap_analysis_moderate_and_missing(
    detector: UncertaintyDetector,
    gap_analyzer: GapAnalyzer,
) -> None:
    role = _role(must_have=["skill:python", "skill:fastapi"])
    graph = _graph(
        nodes=[
            _node("skill:python", confidence=0.95),
            _node("skill:fastapi", confidence=0.4),
        ],
        ledger=[
            _ledger_entry("skill:python", evidence_id="ev_py", confidence=0.92),
            _ledger_entry("skill:fastapi", evidence_id="ev_fa", confidence=0.4),
        ],
    )
    claims: list[ReasoningClaim] = []
    gaps = gap_analyzer.analyze(graph, role, claims)
    result = detector.detect(graph, role, claims, gaps)
    assert gaps.total_count() >= 1
    assert result.total_count() >= 1
