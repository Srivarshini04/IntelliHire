"""PipelineRuntime — generic async stage executor over a shared PipelineContext.

Responsibilities: stage ordering, async execution, context propagation, timing,
logging, telemetry, error propagation, and cancellation. It knows nothing about
evidence, graphs, reasoning, or ranking — only how to run Stages in order.
"""

from __future__ import annotations

import asyncio
import logging
import time

from app.runtime.stage import Stage
from app.shared.context import PipelineContext

logger = logging.getLogger(__name__)


class StageError(RuntimeError):
    """Wraps a failure raised by a stage, tagged with the stage name."""

    def __init__(self, stage_name: str, original: BaseException) -> None:
        super().__init__(f"stage '{stage_name}' failed: {original!r}")
        self.stage_name = stage_name
        self.original = original


class PipelineRuntime:
    """Execute an ordered list of Stages against one PipelineContext.

    Current behaviour is intentionally a simple sequential executor and must stay
    that way for now.

    Future capabilities (documentation only — NOT implemented):
    parallel stages, conditional stages, retries, timeouts, circuit breakers,
    fan-out, fan-in, caching, metrics, tracing, rollback, checkpointing. Each can
    be added behind this same ``run(ctx)`` surface without changing any Stage,
    the CandidateEvaluationPipeline, or the RankingOrchestrator.
    """

    def __init__(
        self,
        stages: list[Stage],
        *,
        name: str = "candidate_pipeline",
        fail_fast: bool = True,
        logger_: logging.Logger | None = None,
    ) -> None:
        self.stages = list(stages)
        self.name = name
        self.fail_fast = fail_fast
        self._log = logger_ or logger

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        """Run every stage in order. On failure, propagate (fail_fast) or warn + continue.

        Re-raises ``asyncio.CancelledError`` immediately. Records per-stage timing +
        status into ``ctx.telemetry['stages']`` and total wall time into
        ``ctx.telemetry['total_ms']``.
        """
        ctx.telemetry.setdefault("stages", {})
        run_start = time.perf_counter()

        for stage in self.stages:
            ctx.mark_stage(stage.name)
            start = time.perf_counter()
            try:
                await stage.run(ctx)
            except asyncio.CancelledError:
                self._log.warning("pipeline '%s' cancelled during stage '%s'", self.name, stage.name)
                self._record(ctx, stage.name, start, "cancelled", "CancelledError")
                raise
            except Exception as exc:  # noqa: BLE001 — runtime boundary; we classify + propagate
                self._log.exception("stage '%s' failed in pipeline '%s'", stage.name, self.name)
                self._record(ctx, stage.name, start, "error", repr(exc))
                if self.fail_fast:
                    raise StageError(stage.name, exc) from exc
                ctx.add_warning(f"stage '{stage.name}' failed: {exc}")
                continue
            self._record(ctx, stage.name, start, "ok", None)

        ctx.telemetry["total_ms"] = round((time.perf_counter() - run_start) * 1000, 3)
        ctx.stage = None
        return ctx

    @staticmethod
    def _record(ctx: PipelineContext, name: str, start: float, status: str, error: str | None) -> None:
        entry: dict = {"duration_ms": round((time.perf_counter() - start) * 1000, 3), "status": status}
        if error:
            entry["error"] = error
        ctx.telemetry["stages"][name] = entry
