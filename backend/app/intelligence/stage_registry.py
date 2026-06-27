"""Dynamic stage registry for document intelligence runtime."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from inspect import isawaitable
from typing import Any

from app.intelligence.pipeline_context import PipelineContext

StageFn = Callable[[PipelineContext], Any | Awaitable[Any]]


class StageRegistry:
    def __init__(self) -> None:
        self._stages: dict[str, StageFn] = {}

    def register(self, name: str, stage_fn: StageFn) -> None:
        self._stages[name] = stage_fn

    def get(self, name: str) -> StageFn:
        if name not in self._stages:
            raise KeyError(f"Stage '{name}' is not registered")
        return self._stages[name]

    def has(self, name: str) -> bool:
        return name in self._stages

    def list(self) -> list[str]:
        return list(self._stages.keys())

    def clear(self) -> None:
        self._stages.clear()

    async def execute(self, name: str, context: PipelineContext) -> Any:
        stage = self.get(name)
        result = stage(context)
        if isawaitable(result):
            return await result
        return result
