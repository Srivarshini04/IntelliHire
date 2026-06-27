"""LLM provider abstraction — engines depend on generate_json(), never on Gemini directly."""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(Protocol):
  async def generate_json(
    self,
    prompt: str,
    schema: type[T],
    *,
    system: str | None = None,
    temperature: float = 0.1,
  ) -> T: ...

  async def generate_text(
    self,
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.1,
  ) -> str: ...

  @property
  def model_name(self) -> str: ...
