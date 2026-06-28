"""Deterministic mock engines implementing the frozen DELULU v2 interfaces.

These are TEST DOUBLES standing in for the other developers' modules
(EvidenceProvider, GraphBuilder, FusionEngine, ReasoningEngine, DecisionEngine) so
the orchestration layer can be exercised end-to-end. They are intentionally minimal
and deterministic — NOT real implementations.
"""

from __future__ import annotations

from typing import Any

from app.shared.enums import (
    EvidenceSource,
    EvidenceType,
    GapSeverity,
    GraphEdgeType,
    GraphNodeType,
    Intensity,
    RecommendationLevel,
)
from app.shared.models import (
    CandidateGap,
    CandidateGraph,
    CandidateReasoning,
    Evidence,
    GraphEdge,
    GraphNode,
    HiringDecision,
    ReasoningClaim,
    RoleDNA,
)


class MockEvidenceProvider:
    """Emit one SKILL Evidence per skill found in the raw source payload."""

    def __init__(self, source: EvidenceSource) -> None:
        self.source = source

    async def collect(self, candidate_id: str, raw: dict[str, Any]) -> list[Evidence]:
        skills = raw.get("skills") or ["python"]
        return [
            Evidence(
                evidence_id=f"ev:{self.source.value}:{candidate_id}:{i}",
                candidate_id=candidate_id,
                source=self.source,
                evidence_type=EvidenceType.SKILL,
                entity_ref=f"skill:{s}",
                claim=f"{candidate_id} uses {s} ({self.source.value})",
                confidence=0.9,
            )
            for i, s in enumerate(skills)
        ]


class MockGraphBuilder:
    """Build a candidate node + one SKILL node/edge per distinct evidence entity."""

    async def build(
        self, candidate_id: str, evidence: list[Evidence], job_id: str | None = None
    ) -> CandidateGraph:
        cand = GraphNode(id=f"candidate:{candidate_id}", type=GraphNodeType.CANDIDATE, label=candidate_id)
        nodes: list[GraphNode] = [cand]
        edges: list[GraphEdge] = []
        seen: set[str] = set()
        for e in evidence:
            if e.entity_ref in seen:
                # attach extra corroborating evidence to the existing node
                node = next(n for n in nodes if n.id == e.entity_ref)
                node.evidence_ids.append(e.evidence_id)
                continue
            seen.add(e.entity_ref)
            nodes.append(
                GraphNode(
                    id=e.entity_ref,
                    type=GraphNodeType.SKILL,
                    label=e.entity_ref.split(":")[-1],
                    evidence_ids=[e.evidence_id],
                )
            )
            edges.append(
                GraphEdge(
                    source_id=cand.id,
                    target_id=e.entity_ref,
                    type=GraphEdgeType.HAS_SKILL,
                    evidence_ids=[e.evidence_id],
                )
            )
        return CandidateGraph(
            graph_id=f"graph:{candidate_id}:{job_id}",
            candidate_id=candidate_id,
            job_id=job_id,
            nodes=nodes,
            edges=edges,
        )


class MockFusionEngine:
    """Set node confidence as a deterministic function of corroborating evidence count."""

    async def fuse(self, graph: CandidateGraph) -> CandidateGraph:
        for node in graph.nodes:
            if node.type == GraphNodeType.SKILL:
                node.confidence = round(min(1.0, 0.6 + 0.1 * len(node.evidence_ids)), 4)
        return graph


class MockReasoningEngine:
    """One claim per skill node; gaps for must-have skills that are absent (Decision C)."""

    async def reason(self, graph: CandidateGraph, role: RoleDNA) -> CandidateReasoning:
        skills = [n for n in graph.nodes if n.type == GraphNodeType.SKILL]
        claims = [
            ReasoningClaim(
                claim_id=f"cl:{n.id}",
                statement=f"has {n.label}",
                entity_refs=[n.id],
                supporting_evidence_ids=list(n.evidence_ids),
                confidence=n.confidence,
                materiality=Intensity.MEDIUM,
                conclusion=f"demonstrates {n.label}",
            )
            for n in skills
        ]
        have = {n.label for n in skills}
        gaps = [
            CandidateGap(requirement=f"missing {s}", entity_ref=f"skill:{s}", severity=GapSeverity.MODERATE)
            for s in role.must_have_skills
            if s not in have
        ]
        overall = round(sum(c.confidence for c in claims) / len(claims), 4) if claims else 0.0
        return CandidateReasoning(
            reasoning_id=f"reasoning:{graph.candidate_id}:{role.job_id}",
            candidate_id=graph.candidate_id,
            job_id=role.job_id,
            claims=claims,
            gaps=gaps,
            overall_confidence=overall,
            summary=f"{len(claims)} capabilities, {len(gaps)} gaps",
        )


class MockDecisionEngine:
    """Deterministic score: rewards #capabilities, penalises #gaps (no randomness)."""

    async def decide(self, reasoning: CandidateReasoning, role: RoleDNA) -> HiringDecision:
        n_claims = len(reasoning.claims)
        n_gaps = len(reasoning.gaps)
        score = max(0.0, min(1.0, round(0.4 + 0.1 * n_claims - 0.15 * n_gaps, 4)))
        rec = (
            RecommendationLevel.STRONG_HIRE if score >= 0.8
            else RecommendationLevel.HIRE if score >= 0.6
            else RecommendationLevel.LEAN_HIRE if score >= 0.4
            else RecommendationLevel.NO_HIRE
        )
        return HiringDecision(
            decision_id=f"decision:{reasoning.candidate_id}:{role.job_id}",
            candidate_id=reasoning.candidate_id,
            job_id=role.job_id,
            recommendation=rec,
            confidence=reasoning.overall_confidence,
            derived_score=score,
            reasons=[c.conclusion for c in reasoning.claims[:3]],
            reservations=[g.requirement for g in reasoning.gaps],
            summary=f"{rec.value} (score {score}) for {reasoning.candidate_id}",
        )


__all__ = [
    "MockEvidenceProvider",
    "MockGraphBuilder",
    "MockFusionEngine",
    "MockReasoningEngine",
    "MockDecisionEngine",
]
