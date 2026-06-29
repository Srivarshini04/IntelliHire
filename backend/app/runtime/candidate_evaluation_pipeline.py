"""CandidateEvaluationPipeline — per-candidate orchestration.

Runs the frozen engine chain (Evidence -> Graph -> Fusion -> Reasoning ->
Decision) for ONE candidate against ONE role, through the generic PipelineRuntime,
and returns the resulting HiringDecision.

Contains NO extraction/graph/reasoning/decision logic — only wiring. Every engine
is injected as its frozen interface, so the other developers plug in their
implementations without touching this file.
"""

from __future__ import annotations

import logging
from typing import Any

from app.runtime.pipeline_runtime import PipelineRuntime
from app.runtime.stages import (
    DecisionStage,
    EvidenceStage,
    FusionStage,
    GraphStage,
    ReasoningStage,
)
from app.shared.context import PipelineContext
from app.shared.interfaces import (
    DecisionEngine,
    EvidenceProvider,
    FusionEngine,
    GraphBuilder,
    ReasoningEngine,
)
from app.shared.models import HiringDecision, RoleDNA

logger = logging.getLogger(__name__)


class PipelineError(RuntimeError):
    """The pipeline completed without producing the expected output."""


class CandidateEvaluationPipeline:
    """Evaluate one candidate for one role and return a HiringDecision."""

    def __init__(
        self,
        *,
        evidence_providers: list[EvidenceProvider],
        graph_builder: GraphBuilder,
        fusion_engine: FusionEngine,
        reasoning_engine: ReasoningEngine,
        decision_engine: DecisionEngine,
        fail_fast: bool = True,
    ) -> None:
        self._runtime = PipelineRuntime(
            [
                EvidenceStage(evidence_providers),
                GraphStage(graph_builder),
                FusionStage(fusion_engine),
                ReasoningStage(reasoning_engine),
                DecisionStage(decision_engine),
            ],
            name="candidate_evaluation",
            fail_fast=fail_fast,
        )

    async def evaluate_to_context(
        self,
        *,
        candidate_id: str,
        job_id: str,
        role_dna: RoleDNA,
        raw_sources: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> PipelineContext:
        """Run the chain and return the full PipelineContext (evidence/graph/.../decision)."""
        ctx = PipelineContext(
            request_id=request_id or f"req:{job_id}:{candidate_id}",
            candidate_id=candidate_id,
            job_id=job_id,
            role_dna=role_dna,
            raw_sources=raw_sources or {},
        )
        return await self._runtime.run(ctx)

    async def evaluate(
        self,
        *,
        candidate_id: str,
        job_id: str,
        role_dna: RoleDNA,
        raw_sources: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> HiringDecision:
        """Run the chain and return only the HiringDecision (raises if none produced)."""
        ctx = await self.evaluate_to_context(
            candidate_id=candidate_id,
            job_id=job_id,
            role_dna=role_dna,
            raw_sources=raw_sources,
            request_id=request_id,
        )
        if ctx.decision is None:
            raise PipelineError(
                f"candidate '{candidate_id}' produced no HiringDecision (last stage: {ctx.stage})"
            )
        return ctx.decision
