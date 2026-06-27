"""Reusable telemetry models for intelligence pipelines."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OrchestratorTelemetry(BaseModel):
    document_id: str
    stage: str = ""

    processing_time_ms: float = 0.0
    llm_latency_ms: float = 0.0
    stage_timings_ms: dict[str, float] = Field(default_factory=dict)

    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    token_usage: int = 0
    provider: str = ""
    model: str = ""
    latency_ms: float = 0.0
    usd_cost: float = 0.0

    retry_count: int = 0
    artifact_count: int = 0
    validation_errors: list[str] = Field(default_factory=list)
    average_confidence: float = 0.0
    document_quality: float = 0.0

    section_count: int = 0
    section_detection_ms: float = 0.0
    normalization_ms: float = 0.0
    extraction_ms: float = 0.0
    validation_ms: float = 0.0
    persistence_ms: float = 0.0

    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
