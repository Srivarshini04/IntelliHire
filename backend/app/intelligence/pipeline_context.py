"""Shared pipeline context object passed across runtime stages."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.intelligence.telemetry import OrchestratorTelemetry
from app.schemas.document import Document


class PipelineContext(BaseModel):
    document: Document
    sections: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    blueprint: Any | None = None
    profile: Any | None = None

    telemetry: OrchestratorTelemetry
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    validation: dict[str, Any] = Field(default_factory=dict)
    knowledge: dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}
