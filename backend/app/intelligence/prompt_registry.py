"""Config-driven prompt registry with version and model metadata."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PromptSpec(BaseModel):
    name: str
    version: str
    provider: str
    model: str
    temperature: float = 0.1
    template: str
    output_schema: str = ""
    few_shot_examples: list[dict[str, Any]] = Field(default_factory=list)


class PromptRegistry:
    def __init__(self) -> None:
        self._prompts: dict[str, dict[str, PromptSpec]] = {}

    def register(self, spec: PromptSpec) -> None:
        versions = self._prompts.setdefault(spec.name, {})
        versions[spec.version] = spec

    def get(self, name: str, version: str | None = None) -> PromptSpec:
        versions = self._prompts.get(name, {})
        if not versions:
            raise KeyError(f"Prompt '{name}' is not registered")
        if version:
            if version not in versions:
                raise KeyError(f"Prompt '{name}' version '{version}' not found")
            return versions[version]
        latest = sorted(versions.keys())[-1]
        return versions[latest]

    def list(self, name: str | None = None) -> dict[str, list[str]]:
        if name:
            return {name: sorted(self._prompts.get(name, {}).keys())}
        return {key: sorted(value.keys()) for key, value in self._prompts.items()}
