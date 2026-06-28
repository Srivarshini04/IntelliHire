"""Stage adapters — one per frozen engine interface.

Each adapter is pure orchestration glue: pull inputs off the PipelineContext, call
the injected interface implementation, store the result back on the context. There
is deliberately NO evidence/graph/reasoning/decision logic here — that belongs to
the other developers' engine implementations.
"""

from __future__ import annotations

import asyncio

from app.runtime.stage import Stage, StageInputError
from app.shared.context import PipelineContext
from app.shared.interfaces import (
    DecisionEngine,
    EvidenceProvider,
    FusionEngine,
    GraphBuilder,
    ReasoningEngine,
)


class EvidenceStage(Stage):
    """Collect Evidence from every provider over ctx.raw_sources (run concurrently)."""

    name = "evidence"

    def __init__(self, providers: list[EvidenceProvider]) -> None:
        self.providers = list(providers)

    async def run(self, ctx: PipelineContext) -> None:
        if not self.providers:
            return

        async def _collect(provider: EvidenceProvider):
            raw = ctx.raw_sources.get(provider.source.value, {})
            return await provider.collect(ctx.candidate_id, raw)

        for batch in await asyncio.gather(*[_collect(p) for p in self.providers]):
            ctx.evidence.extend(batch)


class GraphStage(Stage):
    """Assemble Evidence into a CandidateGraph."""

    name = "graph"

    def __init__(self, builder: GraphBuilder) -> None:
        self.builder = builder

    async def run(self, ctx: PipelineContext) -> None:
        ctx.graph = await self.builder.build(ctx.candidate_id, ctx.evidence, ctx.job_id)


class FusionStage(Stage):
    """Fuse multi-source confidence into the graph nodes."""

    name = "fusion"

    def __init__(self, fusion: FusionEngine) -> None:
        self.fusion = fusion

    async def run(self, ctx: PipelineContext) -> None:
        if ctx.graph is None:
            raise StageInputError("fusion requires a CandidateGraph on the context")
        ctx.graph = await self.fusion.fuse(ctx.graph)


class ReasoningStage(Stage):
    """Reason over (CandidateGraph + RoleDNA) -> CandidateReasoning."""

    name = "reasoning"

    def __init__(self, reasoner: ReasoningEngine) -> None:
        self.reasoner = reasoner

    async def run(self, ctx: PipelineContext) -> None:
        if ctx.graph is None:
            raise StageInputError("reasoning requires a CandidateGraph on the context")
        if ctx.role_dna is None:
            raise StageInputError("reasoning requires RoleDNA on the context")
        ctx.reasoning = await self.reasoner.reason(ctx.graph, ctx.role_dna)


class DecisionStage(Stage):
    """Turn CandidateReasoning into a HiringDecision."""

    name = "decision"

    def __init__(self, decider: DecisionEngine) -> None:
        self.decider = decider

    async def run(self, ctx: PipelineContext) -> None:
        if ctx.reasoning is None:
            raise StageInputError("decision requires CandidateReasoning on the context")
        if ctx.role_dna is None:
            raise StageInputError("decision requires RoleDNA on the context")
        ctx.decision = await self.decider.decide(ctx.reasoning, ctx.role_dna)
