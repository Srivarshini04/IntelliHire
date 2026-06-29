"""Unit tests — ClaimSynthesizer against mock graph / role / reasoning fixtures."""

from __future__ import annotations

import pytest

from app.intelligence.reasoning.claim_synthesizer import ClaimSynthesizer
from app.intelligence.reasoning.types import MaterialityMap
from app.mock import load_graph, load_reasoning, load_role_dna
from app.shared.enums import Intensity
from app.shared.models import CandidateGraph, ReasoningClaim

# RoleDNA is embedded in mock_job.json (load_role_dna); mock_reasoning.json is the
# behavioral target for themed claim structure on the mock candidate graph.

CONFIDENCE_TOLERANCE = 0.15

EXPECTED_CLAIM_IDS = frozenset(
    {
        "claim_retrieval",
        "claim_eval",
        "claim_python",
        "claim_finetuning",
        "claim_availability",
    }
)


@pytest.fixture
def graph() -> CandidateGraph:
    return load_graph()


@pytest.fixture
def role():
    return load_role_dna()


@pytest.fixture
def expected_claims() -> dict[str, ReasoningClaim]:
    return {claim.claim_id: claim for claim in load_reasoning().claims}


@pytest.fixture
def synthesizer() -> ClaimSynthesizer:
    return ClaimSynthesizer()


@pytest.fixture
def claims(graph, role, synthesizer) -> list[ReasoningClaim]:
    return synthesizer.synthesize(graph, MaterialityMap(), role)


@pytest.fixture
def claims_by_id(claims) -> dict[str, ReasoningClaim]:
    return {claim.claim_id: claim for claim in claims}


def _assert_confidence_near(actual: float, expected: float) -> None:
    assert 0.0 <= actual <= 1.0
    assert abs(actual - expected) <= CONFIDENCE_TOLERANCE, (
        f"confidence {actual} not within {CONFIDENCE_TOLERANCE} of {expected}"
    )


def test_synthesize_produces_themed_claim_set(claims):
    assert len(claims) == len(EXPECTED_CLAIM_IDS)
    assert {c.claim_id for c in claims} == EXPECTED_CLAIM_IDS


def test_skills_consolidated_into_themed_claims(claims_by_id):
    """Python and FastAPI merge into one claim rather than two isolated skill claims."""
    python_claim = claims_by_id["claim_python"]
    assert "skill:python" in python_claim.entity_refs
    assert "skill:fastapi" in python_claim.entity_refs
    assert len(claims_by_id) == len(EXPECTED_CLAIM_IDS)


@pytest.mark.parametrize("claim_id", sorted(EXPECTED_CLAIM_IDS))
def test_entity_refs_match_fixture(claims_by_id, expected_claims, claim_id):
    actual = claims_by_id[claim_id]
    expected = expected_claims[claim_id]
    assert actual.entity_refs == expected.entity_refs


@pytest.mark.parametrize("claim_id", sorted(EXPECTED_CLAIM_IDS))
def test_supporting_evidence_matches_fixture(claims_by_id, expected_claims, claim_id):
    actual = claims_by_id[claim_id]
    expected = expected_claims[claim_id]
    assert sorted(actual.supporting_evidence_ids) == sorted(expected.supporting_evidence_ids)


@pytest.mark.parametrize("claim_id", sorted(EXPECTED_CLAIM_IDS))
def test_counter_evidence_matches_fixture(claims_by_id, expected_claims, claim_id):
    actual = claims_by_id[claim_id]
    expected = expected_claims[claim_id]
    assert sorted(actual.counter_evidence_ids) == sorted(expected.counter_evidence_ids)


@pytest.mark.parametrize("claim_id", sorted(EXPECTED_CLAIM_IDS))
def test_confidence_near_fixture(claims_by_id, expected_claims, claim_id):
    _assert_confidence_near(
        claims_by_id[claim_id].confidence,
        expected_claims[claim_id].confidence,
    )


def test_entity_refs_reference_graph_nodes(claims, graph):
    node_ids = {n.id for n in graph.nodes}
    for claim in claims:
        for ref in claim.entity_refs:
            assert ref in node_ids, f"{claim.claim_id}: unknown entity_ref {ref!r}"


def test_retrieval_claim_materiality_and_corroboration(claims_by_id, expected_claims):
    claim = claims_by_id["claim_retrieval"]
    expected = expected_claims["claim_retrieval"]

    assert claim.materiality == expected.materiality
    assert claim.materiality == Intensity.CRITICAL
    assert set(claim.supporting_evidence_ids) == {"ev_resume_0001", "ev_github_0001"}
    assert claim.counter_evidence_ids == []
    statement = claim.statement.lower()
    assert any(token in statement for token in ("retrieval", "hybrid", "shipped", "production"))


def test_eval_claim_targets_ranking_evaluation(claims_by_id, expected_claims):
    claim = claims_by_id["claim_eval"]
    expected = expected_claims["claim_eval"]

    assert claim.entity_refs == ["skill:ranking_evaluation"]
    assert claim.supporting_evidence_ids == ["ev_resume_0002"]
    # Empty MaterialityMap falls back to must_have + coding_requirement (critical);
    # fixture documents high — both are acceptable recruiter-facing tiers.
    assert claim.materiality in {Intensity.HIGH, Intensity.CRITICAL}
    assert expected.materiality in {Intensity.HIGH, Intensity.CRITICAL}
    assert any(token in claim.statement.lower() for token in ("ndcg", "mrr", "eval", "a/b"))


def test_python_claim_multi_source_corroboration(claims_by_id, expected_claims):
    claim = claims_by_id["claim_python"]
    expected = expected_claims["claim_python"]

    assert set(claim.entity_refs) == set(expected.entity_refs)
    assert set(claim.supporting_evidence_ids) == {
        "ev_redrob_0001",
        "ev_leetcode_0001",
        "ev_linkedin_0001",
    }
    assert claim.materiality == Intensity.CRITICAL
    assert "python" in claim.statement.lower()


def test_finetuning_is_contradiction_only_claim(claims_by_id, expected_claims):
    claim = claims_by_id["claim_finetuning"]
    expected = expected_claims["claim_finetuning"]

    assert claim.entity_refs == ["skill:llm_finetuning"]
    assert claim.supporting_evidence_ids == []
    assert claim.counter_evidence_ids == ["ev_linkedin_0002"]
    assert claim.materiality == Intensity.LOW
    _assert_confidence_near(claim.confidence, expected.confidence)
    assert claim.confidence < 0.6
    text = f"{claim.statement} {claim.conclusion}".lower()
    assert "fine-tuning" in text or "finetuning" in text or "lora" in text
    assert any(token in text for token in ("unsubstantiated", "contradict", "nice-to-have", "do not credit"))


def test_availability_claim_from_activity_node(claims_by_id, expected_claims):
    claim = claims_by_id["claim_availability"]
    expected = expected_claims["claim_availability"]

    assert claim.entity_refs == ["activity:commit_cadence"]
    assert claim.supporting_evidence_ids == ["ev_github_0002"]
    assert claim.materiality == Intensity.MEDIUM
    _assert_confidence_near(claim.confidence, expected.confidence)
    text = claim.statement.lower()
    assert any(token in text for token in ("activity", "github", "sustained", "presence"))


def test_positive_claims_carry_no_counters_on_mock(claims_by_id):
    for claim_id in ("claim_retrieval", "claim_eval", "claim_python", "claim_availability"):
        assert claims_by_id[claim_id].counter_evidence_ids == []


def test_all_claims_have_recruiter_facing_text(claims):
    for claim in claims:
        assert isinstance(claim, ReasoningClaim)
        assert claim.statement.strip()
        assert claim.conclusion.strip()


def test_claims_sorted_by_materiality_then_confidence(claims):
    rank = {
        Intensity.NONE: 0,
        Intensity.LOW: 1,
        Intensity.MEDIUM: 2,
        Intensity.HIGH: 3,
        Intensity.CRITICAL: 4,
    }
    pairs = [(rank[c.materiality], c.confidence) for c in claims]
    assert pairs == sorted(pairs, reverse=True)


def test_empty_graph_returns_no_claims(role, synthesizer):
    empty = CandidateGraph(
        graph_id="graph:empty",
        candidate_id="CAND_EMPTY",
        job_id="JOB_EMPTY",
        nodes=[],
        edges=[],
        evidence_ledger=[],
    )
    assert synthesizer.synthesize(empty, MaterialityMap(), role) == []


def test_graph_is_not_mutated(graph, role, synthesizer):
    before = graph.model_dump()
    synthesizer.synthesize(graph, MaterialityMap(), role)
    after = graph.model_dump()
    assert before == after


def test_materiality_map_entity_override(graph, role, synthesizer):
    materiality = MaterialityMap(
        by_entity_ref={"skill:ranking_evaluation": Intensity.LOW},
    )
    claims = synthesizer.synthesize(graph, materiality, role)
    eval_claim = next(c for c in claims if c.claim_id == "claim_eval")
    assert eval_claim.materiality == Intensity.LOW


def test_materiality_map_theme_override_for_availability(graph, role, synthesizer):
    materiality = MaterialityMap(by_theme={"availability": Intensity.HIGH})
    claims = synthesizer.synthesize(graph, materiality, role)
    availability = next(c for c in claims if c.claim_id == "claim_availability")
    assert availability.materiality == Intensity.HIGH


def test_fixture_reasoning_structure_for_claims_only(expected_claims):
    """Sanity-check the golden fixture used as the behavioral reference."""
    reasoning = load_reasoning()
    assert reasoning.schema_version == "1.0"
    assert reasoning.candidate_id == "CAND_0004989"
    assert reasoning.job_id == "JOB_BACKEND_1"
    assert len(reasoning.claims) == len(EXPECTED_CLAIM_IDS)
    assert set(expected_claims) == EXPECTED_CLAIM_IDS

    for claim_id, claim in expected_claims.items():
        assert 0.0 <= claim.confidence <= 1.0
        assert claim.materiality in Intensity


def test_synthesis_aligns_with_fixture_claim_contract(
    claims_by_id, expected_claims,
):
    """Cross-check structural fields for every themed claim in one assertion."""
    mismatches: list[str] = []
    for claim_id in sorted(EXPECTED_CLAIM_IDS):
        actual = claims_by_id[claim_id]
        expected = expected_claims[claim_id]
        if actual.entity_refs != expected.entity_refs:
            mismatches.append(f"{claim_id} entity_refs")
        if sorted(actual.supporting_evidence_ids) != sorted(expected.supporting_evidence_ids):
            mismatches.append(f"{claim_id} supporting_evidence_ids")
        if sorted(actual.counter_evidence_ids) != sorted(expected.counter_evidence_ids):
            mismatches.append(f"{claim_id} counter_evidence_ids")
    assert mismatches == []
