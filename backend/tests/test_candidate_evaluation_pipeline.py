"""Integration / runtime tests.

Verifies the full owned chain with mock engines standing in for the other
developers' modules:

    RoleBlueprint -> RoleDNA -> PipelineRuntime
    -> (Evidence -> Graph -> Fusion -> Reasoning -> Decision) -> HiringDecision
    -> RankingOrchestrator + DeterministicRankingEngine -> RankedList
"""

from __future__ import annotations

import asyncio

import pytest
from mocks import (
    MockDecisionEngine,
    MockEvidenceProvider,
    MockFusionEngine,
    MockGraphBuilder,
    MockReasoningEngine,
)

from app.intelligence.role_dna import BlueprintRoleDNAProvider
from app.runtime import (
    DeterministicRankingEngine,
    CandidateEvaluationPipeline,
    PipelineError,
    RankingOrchestrator,
)
from app.shared.enums import EvidenceSource, RankingStage
from app.shared.models import HiringDecision, RankedList, RoleDNA

run = asyncio.run

BLUEPRINT = {
    "role_title": {"value": "Senior Backend Engineer"},
    "experience_level": {"value": "6 years"},
    "required_skills": [{"normalized_name": "python"}, {"normalized_name": "fastapi"}],
    "capability_weights": {"backend": 1.0},
}


def _pipeline(**override) -> CandidateEvaluationPipeline:
    cfg = dict(
        evidence_providers=[
            MockEvidenceProvider(EvidenceSource.GITHUB),
            MockEvidenceProvider(EvidenceSource.RESUME),
        ],
        graph_builder=MockGraphBuilder(),
        fusion_engine=MockFusionEngine(),
        reasoning_engine=MockReasoningEngine(),
        decision_engine=MockDecisionEngine(),
    )
    cfg.update(override)
    return CandidateEvaluationPipeline(**cfg)


def _role(job_id: str = "JOB_BACKEND_1") -> RoleDNA:
    return run(BlueprintRoleDNAProvider().build(job_id, blueprint=BLUEPRINT))


def test_pipeline_produces_hiring_decision():
    ctx = run(
        _pipeline().evaluate_to_context(
            candidate_id="C1",
            job_id="JOB_BACKEND_1",
            role_dna=_role(),
            raw_sources={"github": {"skills": ["python", "fastapi"]}, "resume": {"skills": ["sql"]}},
        )
    )
    assert len(ctx.evidence) == 3
    assert ctx.graph is not None and ctx.reasoning is not None and ctx.decision is not None
    assert set(ctx.telemetry["stages"]) == {"evidence", "graph", "fusion", "reasoning", "decision"}
    assert isinstance(ctx.decision, HiringDecision)


def test_missing_decision_raises_pipeline_error():
    class _NullDecision(MockDecisionEngine):
        async def decide(self, reasoning, role):  # type: ignore[override]
            return None

    with pytest.raises(PipelineError):
        run(_pipeline(decision_engine=_NullDecision()).evaluate(
            candidate_id="C1", job_id="JOB_BACKEND_1", role_dna=_role()))


def test_end_to_end_blueprint_to_ranking():
    role = _role()
    # Canonical entity refs (match CandidateGraph node ids), not bare skill names.
    assert isinstance(role, RoleDNA) and role.must_have_skills == ["skill:python", "skill:fastapi"]

    orch = RankingOrchestrator(evaluation_pipeline=_pipeline(), ranking_engine=DeterministicRankingEngine())
    candidates = [
        {"candidate_id": "strong", "raw_sources": {"github": {"skills": ["python", "fastapi", "sql"]}}},
        {"candidate_id": "weak", "raw_sources": {"github": {"skills": ["python"]}}},
        {"candidate_id": "mid", "raw_sources": {"github": {"skills": ["python", "fastapi"]}}},
    ]
    final = run(orch.rank(job_id="JOB_BACKEND_1", role_dna=role, candidates=candidates, limit=10))

    assert isinstance(final, RankedList) and final.stage == RankingStage.RERANK
    assert len(final.items) == 3
    order = [it.candidate_id for it in final.items]
    assert order[0] == "strong" and order[-1] == "weak"          # more skills, fewer gaps -> higher
    assert [it.rank for it in final.items] == [1, 2, 3]
    assert all(it.reasoning for it in final.items)               # required submission `reasoning`
    assert all(final.items[i].score >= final.items[i + 1].score for i in range(len(final.items) - 1))


def test_two_stage_shortlists_before_ranking():
    orch = RankingOrchestrator(evaluation_pipeline=_pipeline(), ranking_engine=DeterministicRankingEngine())
    cands = [{"candidate_id": f"c{i}", "raw_sources": {"github": {"skills": ["python"]}}} for i in range(5)]
    out = run(orch.run_two_stage(job_id="J1", role_dna=_role("J1"), candidates=cands, top_k=2, limit=10))
    assert len(out.items) == 2


def test_baseline_retrieve_shortlist():
    rows = run(DeterministicRankingEngine().retrieve(
        "J1", RoleDNA(role_dna_id="r", job_id="J1", role_summary=""),
        [{"candidate_id": f"c{i}"} for i in range(4)], top_k=2))
    assert [r.candidate_id for r in rows] == ["c0", "c1"]
    assert all(r.stage == RankingStage.RETRIEVAL for r in rows)
