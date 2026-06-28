"""Validate every mock fixture against the frozen shared models. Run from backend/:
    ../.venv/bin/python -m app.mock._verify
"""
from __future__ import annotations

from app.mock import (
    CANDIDATE_ID,
    JOB_ID,
    load,
    load_decision,
    load_evidence,
    load_graph,
    load_ranking,
    load_reasoning,
    load_role_dna,
)
from app.shared.enums import EvidencePolarity


def main() -> int:
    errs: list[str] = []

    cand = load("mock_candidate")
    assert cand["candidate_id"] == CANDIDATE_ID, "candidate id mismatch"

    job = load("mock_job")
    assert job["job_id"] == JOB_ID, "job id mismatch"

    role = load_role_dna()
    assert role.role_dna_id == "roledna:JOB_BACKEND_1" and role.job_id == JOB_ID

    evidence = load_evidence()
    assert 6 <= len(evidence) <= 10, f"expected 6-10 evidence, got {len(evidence)}"
    contradicts = [e for e in evidence if e.polarity == EvidencePolarity.CONTRADICTS]
    assert contradicts, "no contradicts-polarity evidence found"
    assert all(e.candidate_id == CANDIDATE_ID for e in evidence)

    graph = load_graph()
    assert graph.graph_id == "graph:CAND_0004989:JOB_BACKEND_1"
    assert graph.candidate_id == CANDIDATE_ID and graph.job_id == JOB_ID
    node_ids = {n.id for n in graph.nodes}
    for entry in graph.evidence_ledger:
        assert entry.supporting_node_id in node_ids, (
            f"ledger entry {entry.evidence_id} -> missing node {entry.supporting_node_id}"
        )
    ev_ids = {e.evidence_id for e in evidence}
    for entry in graph.evidence_ledger:
        assert entry.evidence_id in ev_ids, f"ledger ev {entry.evidence_id} not in evidence"

    reasoning = load_reasoning()
    assert reasoning.reasoning_id == "reasoning:CAND_0004989:JOB_BACKEND_1"
    assert any(c.counter_evidence_ids for c in reasoning.claims), "no counter evidence in claims"

    decision = load_decision()
    assert decision.decision_id == "decision:CAND_0004989:JOB_BACKEND_1"

    ranking = load_ranking()
    assert ranking.ranked_list_id == "rankedlist:JOB_BACKEND_1:rerank"
    assert ranking.items[0].candidate_id == CANDIDATE_ID
    scores = [i.score for i in ranking.items]
    assert scores == sorted(scores, reverse=True), "ranking scores not descending"
    assert all(i.reasoning for i in ranking.items), "a ranking row is missing reasoning"
    assert all(i.stage.value == "rerank" for i in ranking.items)

    if errs:
        print("\n".join(errs))
        return 1
    print("ALL MOCK FIXTURES VALIDATE")
    print(f"  evidence items: {len(evidence)} (contradicts: {len(contradicts)})")
    print(f"  graph nodes/edges/ledger: {len(graph.nodes)}/{len(graph.edges)}/{len(graph.evidence_ledger)}")
    print(f"  reasoning claims/gaps: {len(reasoning.claims)}/{len(reasoning.gaps)}")
    print(f"  ranking rows: {len(ranking.items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
