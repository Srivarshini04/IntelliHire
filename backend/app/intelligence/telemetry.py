"""Reusable telemetry models for intelligence pipelines."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class CostMetrics(BaseModel):
    cost_usd: float = 0.0


class OrchestratorTelemetry(BaseModel):
    document_id: str
    stage: str = ""

    processing_time_ms: float = 0.0
    llm_latency_ms: float = 0.0

    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    cost: CostMetrics = Field(default_factory=CostMetrics)

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
