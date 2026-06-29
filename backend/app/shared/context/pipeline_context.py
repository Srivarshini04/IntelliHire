"""PipelineContext — the single carrier object threaded through every v2 stage.

The orchestrator constructs one PipelineContext per (candidate, job) and hands it
to each engine in turn. Each engine reads what it needs and writes its output back
onto the context. Fields fill in roughly top-to-bottom as the pipeline advances.

NOTE: distinct from ``app.intelligence.pipeline_context.PipelineContext`` (which is
document-extraction stage state). This is the *candidate-evaluation* carrier.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.shared.models import (
    CandidateGraph,
    CandidateRanking,
    CandidateReasoning,
    Evidence,
    HiringDecision,
    RoleDNA,
)


class PipelineContext(BaseModel):
    """Mutable per-(candidate, job) state shared across the pipeline."""

    # --- scope / identity ---
    request_id: str
    candidate_id: str
    job_id: str

    # --- raw inputs (source payloads keyed by source name) ---
    raw_sources: dict[str, Any] = Field(
        default_factory=dict,
        description="e.g. {'github': {...}, 'resume_text': '...', 'redrob': {...}}.",
    )

    # --- role side ---
    role_dna: RoleDNA | None = None

    # --- candidate side (filled progressively by each stage) ---
    evidence: list[Evidence] = Field(default_factory=list)
    graph: CandidateGraph | None = None
    reasoning: CandidateReasoning | None = None
    decision: HiringDecision | None = None
    ranking: CandidateRanking | None = None

    # --- cross-cutting ---
    stage: str | None = Field(default=None, description="Name of the stage currently executing.")
    warnings: list[str] = Field(default_factory=list)
    telemetry: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def mark_stage(self, name: str) -> None:
        self.stage = name

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)
