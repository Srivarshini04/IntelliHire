"""Stage contract for the DELULU v2 candidate-evaluation runtime.

A Stage is a thin adapter that reads from and writes to the shared
``PipelineContext``. Stages contain NO business logic — they only invoke a frozen
engine interface and store its result on the context.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.shared.context import PipelineContext


class StageInputError(RuntimeError):
    """Raised when a stage's required PipelineContext inputs are missing."""


class Stage(ABC):
    """One step in the runtime. Subclasses set ``name`` and implement ``run``."""

    name: str = "stage"

    @abstractmethod
    async def run(self, ctx: PipelineContext) -> None:
        """Execute the stage, mutating ``ctx`` in place. Must be idempotent-safe."""
        raise NotImplementedError
