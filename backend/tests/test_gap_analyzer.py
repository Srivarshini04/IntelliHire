"""Unit tests — GapAnalyzer (read-only competency gap detection)."""

from __future__ import annotations

import copy

import pytest

from app.intelligence.reasoning.claim_synthesizer import ClaimSynthesizer
from app.intelligence.reasoning.types import MaterialityMap
from app.mock import load_graph, load_role_dna
from app.intelligence.reasoning.gap_analyzer import GapAnalysis, GapAnalyzer, GapItem
from app.shared.enums import EvidencePolarity, EvidenceSource, EvidenceType, GraphNodeType
from app.shared.models import CandidateGraph, GraphNode, ReasoningClaim, RoleDNA
from app.shared.models.evidence import EvidenceLedgerEntry


@pytest.fixture
def analyzer() -> GapAnalyzer:
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
    polarity: EvidencePolarity = EvidencePolarity.SUPPORTS,
    confidence: float = 0.85,
) -> EvidenceLedgerEntry:
    return EvidenceLedgerEntry(
        evidence_id=evidence_id,
        candidate_id="CAND_TEST",
        source=EvidenceSource.RESUME,
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


def test_empty_role_dna_produces_no_gaps(analyzer: GapAnalyzer) -> None:
    result = analyzer.analyze(_graph(), _role(), [])
    assert result.total_count() == 0
    assert result == GapAnalysis()


def test_empty_graph_with_requirements_yields_gaps(analyzer: GapAnalyzer) -> None:
    role = _role(must_have=["skill:python"])
    result = analyzer.analyze(_graph(), role, [])
    assert len(result.critical) == 1
    assert result.critical[0].title == "Python"
    assert "skill:python" in result.critical[0].missing_evidence


def test_one_critical_gap_missing_node(analyzer: GapAnalyzer) -> None:
    role = _role(must_have=["skill:vector_search"])
    result = analyzer.analyze(_graph(), role, [])
    assert result.critical[0].severity == "critical"
    assert result.critical[0].category == "must_have"


def test_one_moderate_gap_weak_evidence(analyzer: GapAnalyzer) -> None:
    role = _role(must_have=["skill:fastapi"])
    graph = _graph(
        nodes=[_node("skill:fastapi", confidence=0.4)],
        ledger=[_ledger_entry("skill:fastapi", confidence=0.4)],
    )
    result = analyzer.analyze(graph, role, [])
    assert result.total_count() == 1
    assert result.moderate[0].severity == "moderate"
    assert result.moderate[0].title.lower() == "fastapi"


def test_one_minor_gap_nice_to_have(analyzer: GapAnalyzer) -> None:
    role = _role(nice_to_have=["skill:kubernetes"])
    result = analyzer.analyze(_graph(), role, [])
    assert len(result.minor) == 1
    assert result.minor[0].category == "nice_to_have"


def test_fully_satisfied_must_have_produces_no_gap(analyzer: GapAnalyzer) -> None:
    role = _role(must_have=["skill:python"])
    graph = _graph(
        nodes=[_node("skill:python", confidence=0.92)],
        ledger=[
            _ledger_entry("skill:python", evidence_id="ev_a", confidence=0.9),
            _ledger_entry("skill:python", evidence_id="ev_b", confidence=0.88),
        ],
    )
    claims = [_claim("skill:python", supporting=["ev_a", "ev_b"], confidence=0.9)]
    result = analyzer.analyze(graph, role, claims)
    assert result.total_count() == 0


def test_multiple_gaps_across_severities(analyzer: GapAnalyzer) -> None:
    role = _role(
        must_have=["skill:python", "skill:vector_search"],
        nice_to_have=["skill:kubernetes"],
    )
    graph = _graph(
        nodes=[_node("skill:python", confidence=0.35)],
        ledger=[_ledger_entry("skill:python", confidence=0.35)],
    )
    result = analyzer.analyze(graph, role, [])
    assert result.total_count() == 3
    assert len(result.critical) == 1
    assert len(result.moderate) == 1
    assert len(result.minor) == 1


def test_no_duplicate_gaps_for_repeated_competency_lists(analyzer: GapAnalyzer) -> None:
    role = RoleDNA(
        role_dna_id="roledna:dup",
        job_id="JOB_TEST",
        role_summary="dup",
        must_have_skills=["skill:python", "skill:python"],
        nice_to_have_skills=["skill:python"],
    )
    result = analyzer.analyze(_graph(), role, [])
    assert result.total_count() == 1


def test_duplicate_ledger_entries_do_not_duplicate_gaps(analyzer: GapAnalyzer) -> None:
    role = _role(must_have=["skill:python"])
    graph = _graph(
        nodes=[_node("skill:python", confidence=0.3)],
        ledger=[
            _ledger_entry("skill:python", evidence_id="ev_dup", confidence=0.3),
            _ledger_entry("skill:python", evidence_id="ev_dup", confidence=0.3),
        ],
    )
    result = analyzer.analyze(graph, role, [])
    assert result.total_count() == 1
    assert len(result.moderate[0].missing_evidence) >= 1


def test_contradiction_only_evidence_is_weak(analyzer: GapAnalyzer) -> None:
    role = _role(nice_to_have=["skill:llm_finetuning"])
    graph = _graph(
        nodes=[_node("skill:llm_finetuning", confidence=0.45)],
        ledger=[
            _ledger_entry(
                "skill:llm_finetuning",
                evidence_id="ev_counter",
                polarity=EvidencePolarity.CONTRADICTS,
                confidence=0.55,
            )
        ],
    )
    claims = [_claim("skill:llm_finetuning", counter=["ev_counter"], confidence=0.4)]
    result = analyzer.analyze(graph, role, claims)
    assert len(result.minor) == 1
    assert "ev_counter" in result.minor[0].missing_evidence


def test_high_materiality_missing_node_is_critical_not_moderate(analyzer: GapAnalyzer) -> None:
    role = _role(must_have=["skill:embeddings_retrieval"])
    result = analyzer.analyze(_graph(), role, [])
    assert result.critical[0].severity == "critical"
    assert result.moderate == []


def test_domain_competency_gap(analyzer: GapAnalyzer) -> None:
    role = _role(domain="talent_intelligence_search_ranking")
    result = analyzer.analyze(_graph(), role, [])
    assert len(result.moderate) == 1
    assert result.moderate[0].category == "domain"


def test_deterministic_ordering(analyzer: GapAnalyzer) -> None:
    role = _role(
        must_have=["skill:zebra", "skill:alpha"],
        nice_to_have=["skill:beta"],
    )
    first = analyzer.analyze(_graph(), role, [])
    second = analyzer.analyze(_graph(), role, [])
    assert first == second
    assert [item.title for item in first.critical] == sorted(
        [item.title for item in first.critical], key=str.lower
    )


def test_inputs_are_not_mutated(analyzer: GapAnalyzer) -> None:
    role = _role(must_have=["skill:python"], nice_to_have=["skill:kubernetes"])
    graph = _graph(nodes=[_node("skill:python", confidence=0.9)])
    claims = [_claim("skill:python", supporting=["ev_a"])]
    role_before = role.model_dump()
    graph_before = graph.model_dump()
    claims_before = [claim.model_dump() for claim in claims]
    analyzer.analyze(graph, role, claims)
    assert role.model_dump() == role_before
    assert graph.model_dump() == graph_before
    assert [c.model_dump() for c in claims] == claims_before


def test_gap_item_fields_populated(analyzer: GapAnalyzer) -> None:
    role = _role(must_have=["skill:python"])
    result = analyzer.analyze(_graph(), role, [])
    item = result.critical[0]
    assert isinstance(item, GapItem)
    assert item.category == "must_have"
    assert item.title
    assert item.severity == "critical"
    assert item.rationale
    assert item.missing_evidence


def test_claim_support_can_satisfy_without_ledger(analyzer: GapAnalyzer) -> None:
    role = _role(must_have=["skill:python"])
    graph = _graph(nodes=[_node("skill:python", confidence=0.9)])
    claims = [_claim("skill:python", supporting=["ev_x"], confidence=0.88)]
    result = analyzer.analyze(graph, role, claims)
    assert result.total_count() == 0


def test_weak_claim_does_not_override_missing_ledger(analyzer: GapAnalyzer) -> None:
    role = _role(must_have=["skill:python"])
    graph = _graph(nodes=[_node("skill:python", confidence=0.9)])
    claims = [_claim("skill:python", supporting=["ev_x"], confidence=0.3)]
    result = analyzer.analyze(graph, role, claims)
    assert result.total_count() >= 1


def test_moderate_gap_for_partial_must_have_coverage(analyzer: GapAnalyzer) -> None:
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
    result = analyzer.analyze(graph, role, [])
    assert result.total_count() == 1
    assert result.moderate[0].title.lower() == "fastapi"


def test_nice_to_have_with_strong_evidence_no_gap(analyzer: GapAnalyzer) -> None:
    role = _role(nice_to_have=["skill:kubernetes"])
    graph = _graph(
        nodes=[_node("skill:kubernetes", confidence=0.88)],
        ledger=[_ledger_entry("skill:kubernetes", confidence=0.86)],
    )
    result = analyzer.analyze(graph, role, [])
    assert result.total_count() == 0


def test_all_items_helper(analyzer: GapAnalyzer) -> None:
    role = _role(must_have=["skill:a"], nice_to_have=["skill:b"])
    result = analyzer.analyze(_graph(), role, [])
    assert len(result.all_items()) == result.total_count()


def test_severity_buckets_exclusive(analyzer: GapAnalyzer) -> None:
    role = _role(
        must_have=["skill:missing_critical"],
        nice_to_have=["skill:missing_minor"],
    )
    result = analyzer.analyze(_graph(), role, [])
    severities = {item.severity for item in result.all_items()}
    assert severities <= {"critical", "moderate", "minor"}


def test_mock_fixture_vector_search_gap(analyzer: GapAnalyzer) -> None:
    graph = load_graph()
    role = load_role_dna()
    claims = ClaimSynthesizer().synthesize(graph, MaterialityMap(), role)
    result = analyzer.analyze(graph, role, claims)
    vector_gaps = [
        item
        for item in result.all_items()
        if "skill:vector_search" in item.missing_evidence
        or "vector_search" in item.rationale
    ]
    assert len(vector_gaps) == 1
    assert vector_gaps[0].severity == "critical"


def test_mock_fixture_llm_finetuning_minor_gap(analyzer: GapAnalyzer) -> None:
    graph = load_graph()
    role = load_role_dna()
    claims = ClaimSynthesizer().synthesize(graph, MaterialityMap(), role)
    result = analyzer.analyze(graph, role, claims)
    minor_titles = {item.title.lower() for item in result.minor}
    assert any("fine" in title or "lora" in title for title in minor_titles)


def test_mock_fixture_satisfied_must_haves_not_gapped(analyzer: GapAnalyzer) -> None:
    graph = load_graph()
    role = load_role_dna()
    claims = ClaimSynthesizer().synthesize(graph, MaterialityMap(), role)
    result = analyzer.analyze(graph, role, claims)
    gapped = {item.title.lower() for item in result.all_items()}
    assert "python" not in gapped
    assert "fastapi" not in gapped


def test_gap_analysis_dataclass_defaults() -> None:
    analysis = GapAnalysis()
    assert analysis.critical == []
    assert analysis.moderate == []
    assert analysis.minor == []
    assert analysis.total_count() == 0


def test_rationale_mentions_entity_ref(analyzer: GapAnalyzer) -> None:
    role = _role(must_have=["skill:python"])
    result = analyzer.analyze(_graph(), role, [])
    assert "skill:python" in result.critical[0].rationale


def test_copy_of_graph_produces_same_gaps(analyzer: GapAnalyzer) -> None:
    role = _role(must_have=["skill:python", "skill:fastapi"])
    graph = _graph(nodes=[_node("skill:python", confidence=0.95)])
    baseline = analyzer.analyze(graph, role, [])
    cloned = CandidateGraph.model_validate(copy.deepcopy(graph.model_dump()))
    assert analyzer.analyze(cloned, role, []) == baseline


def test_empty_claims_list_still_analyzes_graph(analyzer: GapAnalyzer) -> None:
    role = _role(must_have=["skill:python"])
    graph = _graph(
        nodes=[_node("skill:python", confidence=0.95)],
        ledger=[_ledger_entry("skill:python", confidence=0.9)],
    )
    result = analyzer.analyze(graph, role, [])
    assert result.total_count() == 0


def test_critical_bucket_sorted_before_moderate_in_all_items(analyzer: GapAnalyzer) -> None:
    role = _role(
        must_have=["skill:alpha", "skill:beta"],
        nice_to_have=["skill:gamma"],
    )
    result = analyzer.analyze(_graph(), role, [])
    assert result.critical and result.minor
    assert result.all_items()[0].severity == "critical"


def test_missing_evidence_lists_unique_entries(analyzer: GapAnalyzer) -> None:
    role = _role(must_have=["skill:python"])
    result = analyzer.analyze(_graph(), role, [])
    missing = result.critical[0].missing_evidence
    assert missing == list(dict.fromkeys(missing))
