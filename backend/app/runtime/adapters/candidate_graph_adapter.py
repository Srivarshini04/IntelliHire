"""CandidateGraphAdapter — Developer 3 sync GraphBuilder -> v2 GraphBuilder Protocol.

Developer 3's :class:`app.intelligence.candidate_graph.GraphBuilder` is a synchronous,
pure-compute engine (Evidence -> ledger -> entity resolution -> construction -> dedup
-> inference -> confidence fusion -> CandidateGraph). The frozen
:class:`app.shared.interfaces.GraphBuilder` Protocol is ``async``, because the pipeline
``GraphStage`` ``await``s every builder uniformly.

This adapter is the single translation boundary between the two: it exposes the async
``build`` signature and delegates to Developer 3's engine unchanged. The build is
CPU-bound (NetworkX traversal/fusion), so it is offloaded with ``asyncio.to_thread``
to keep the event loop free during batch ranking — the only behavioural addition; the
graph itself is produced entirely by Developer 3's code.

This is the real replacement for ``NoOpGraphAdapter``: it drops into the same DI slot
(``app.runtime.deps.get_graph_builder``) with zero runtime/route/contract changes. The
returned :class:`CandidateGraph` carries populated nodes/edges/evidence_ledger and does
NOT set ``metadata['graph_disabled']`` — that is the switch ``ReasoningEngineAdapter``
reads to run Developer 4's native graph traversal instead of the evidence fallback.
"""

from __future__ import annotations

import asyncio
import logging

from app.intelligence.candidate_graph import GraphBuilder as CandidateGraphBuilder
from app.shared.models import CandidateGraph, Evidence

logger = logging.getLogger(__name__)


class CandidateGraphAdapter:
    """Adapt Developer 3's synchronous ``GraphBuilder`` to the async ``GraphBuilder`` Protocol."""

    def __init__(self, builder: CandidateGraphBuilder | None = None) -> None:
        # Developer 3's engine is reused as-is; never modified or subclassed here.
        self._builder = builder or CandidateGraphBuilder()

    async def build(
        self, candidate_id: str, evidence: list[Evidence], job_id: str | None = None
    ) -> CandidateGraph:
        logger.info(
            "CandidateGraphAdapter.build candidate=%s job=%s evidence=%d",
            candidate_id,
            job_id,
            len(evidence),
        )
        # Offload the CPU-bound, synchronous build so the event loop stays responsive
        # while many candidates are evaluated concurrently during ranking.
        return await asyncio.to_thread(
            self._builder.build,
            candidate_id=candidate_id,
            evidence=evidence,
            job_id=job_id,
        )
