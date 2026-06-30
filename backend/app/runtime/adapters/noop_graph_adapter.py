"""NoOpGraphAdapter — the graph-stage placeholder while Graph Intelligence is absent.

Developer 3's Candidate Graph / Entity Resolution / Confidence Fusion / Evidence
Ledger are NOT implemented. Per the integration rules, we do not implement them and
do not fake graph reasoning. Instead this adapter satisfies the frozen
:class:`app.shared.interfaces.GraphBuilder` Protocol, passes evidence through
unchanged, and emits telemetry recording that the graph stage was skipped — nothing
more. When the real ``CandidateGraphAdapter`` lands it drops into the same DI slot
with zero runtime/API changes.

Also provides :class:`NoOpFusionEngine`: the frozen ``CandidateEvaluationPipeline``
runs a ``FusionStage`` (fusion belongs to Developer 3's graph intelligence). With no
graph there is nothing to fuse, so it returns the graph unchanged. Kept here so all
graph-disabled behaviour lives in one small module.
"""

from __future__ import annotations

import logging

from app.shared.models import CandidateGraph, Evidence

logger = logging.getLogger(__name__)


class NoOpGraphAdapter:
    """``GraphBuilder`` placeholder: empty-topology graph, evidence passed through."""

    async def build(
        self, candidate_id: str, evidence: list[Evidence], job_id: str | None = None
    ) -> CandidateGraph:
        graph_id = f"graph:{candidate_id}" + (f":{job_id}" if job_id else "")
        logger.info(
            "graph stage skipped (NoOpGraphAdapter): passed %d evidence through for candidate %s",
            len(evidence),
            candidate_id,
        )
        # Pass the raw evidence through on metadata (JSON-serializable) so the
        # ReasoningEngineAdapter can reason directly from evidence while Graph
        # Intelligence is absent. nodes/edges/ledger stay empty — we do not build
        # a graph. ``graph_disabled`` is the switch the reasoning adapter reads.
        return CandidateGraph(
            graph_id=graph_id,
            candidate_id=candidate_id,
            job_id=job_id,
            nodes=[],
            edges=[],
            evidence_ledger=[],
            metadata={
                "graph_disabled": True,
                "graph_stage": "skipped",
                "adapter": "NoOpGraphAdapter",
                "reason": "Graph Intelligence (Developer 3) not implemented",
                "evidence_count": len(evidence),
                "evidence": [ev.model_dump(mode="json") for ev in evidence],
            },
        )


class NoOpFusionEngine:
    """``FusionEngine`` no-op: nothing to fuse on an empty graph; returns it unchanged."""

    async def fuse(self, graph: CandidateGraph) -> CandidateGraph:
        graph.metadata.setdefault("fusion_stage", "skipped")
        return graph
