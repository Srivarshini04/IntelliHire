"""Blueprint generation observability metrics."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BlueprintGenerationMetrics(BaseModel):
    document_id: UUID
    processing_time_ms: float = 0.0
    tokens_used: int | None = None
    llm_cost_usd: float | None = None
    prompt_version: str = ""
    parser_version: str = ""
    llm_model: str = ""
    retry_count: int = 0
    validation_errors: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)
    average_confidence: float = 0.0
    document_quality: float = 0.0
    blueprint_version: str = "1.0.0"
    section_count: int = 0
    status: str = "draft"  # draft | failed
    generated_at: datetime = Field(default_factory=datetime.utcnow)
