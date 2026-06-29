"""Unit tests — PipelineRuntime ordering, telemetry, error propagation, cancellation."""

from __future__ import annotations

import asyncio

import pytest

from app.runtime import PipelineRuntime, Stage, StageError
from app.shared.context import PipelineContext

run = asyncio.run


def _ctx() -> PipelineContext:
    return PipelineContext(request_id="r", candidate_id="c", job_id="j")


class _Append(Stage):
    def __init__(self, name: str, token: str) -> None:
        self.name = name
        self.token = token

    async def run(self, ctx: PipelineContext) -> None:
        ctx.metadata.setdefault("order", []).append(self.token)


class _Boom(Stage):
    name = "boom"

    async def run(self, ctx: PipelineContext) -> None:
        raise ValueError("kaboom")


class _Cancel(Stage):
    name = "cancel"

    async def run(self, ctx: PipelineContext) -> None:
        raise asyncio.CancelledError()


def test_runs_stages_in_order():
    ctx = _ctx()
    run(PipelineRuntime([_Append("a", "A"), _Append("b", "B"), _Append("c", "C")]).run(ctx))
    assert ctx.metadata["order"] == ["A", "B", "C"]


def test_telemetry_recorded():
    ctx = _ctx()
    run(PipelineRuntime([_Append("a", "A")]).run(ctx))
    assert ctx.telemetry["stages"]["a"]["status"] == "ok"
    assert "duration_ms" in ctx.telemetry["stages"]["a"]
    assert "total_ms" in ctx.telemetry
    assert ctx.stage is None


def test_fail_fast_raises_stage_error():
    ctx = _ctx()
    with pytest.raises(StageError) as ei:
        run(PipelineRuntime([_Append("a", "A"), _Boom(), _Append("c", "C")]).run(ctx))
    assert ei.value.stage_name == "boom"
    assert isinstance(ei.value.original, ValueError)
    assert "c" not in ctx.telemetry["stages"]  # stopped before stage c


def test_fail_soft_continues_with_warning():
    ctx = _ctx()
    run(PipelineRuntime([_Append("a", "A"), _Boom(), _Append("c", "C")], fail_fast=False).run(ctx))
    assert ctx.metadata["order"] == ["A", "C"]
    assert any("boom" in w for w in ctx.warnings)
    assert ctx.telemetry["stages"]["c"]["status"] == "ok"


def test_cancellation_propagates():
    ctx = _ctx()
    with pytest.raises(asyncio.CancelledError):
        run(PipelineRuntime([_Cancel()]).run(ctx))
    assert ctx.telemetry["stages"]["cancel"]["status"] == "cancelled"
