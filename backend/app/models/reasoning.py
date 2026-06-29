"""candidate_reasoning / candidate_decisions — persistence mirrors of the shared
reasoning + decision models.

PK/id convention (Workstream A):
    * ``id`` (UUID) is the internal DB row PK.
    * The shared *domain* ids ``reasoning_id`` / ``decision_id`` are separate, unique
      String columns.

Separate persistence mirror of ``app.shared.models.reasoning`` — never redefines the
shared Pydantic models. List/dict fields (claims, gaps, uncertainties,
interview_focus, recommendations, metadata) are stored as JSONB; enums as ``.value``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CandidateReasoning(Base):
    """ReasoningEngine output for one (candidate, job) (mirrors CandidateReasoning)."""

    __tablename__ = "candidate_reasoning"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reasoning_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )

    schema_version: Mapped[str] = mapped_column(String(10), default="1.0")
    claims: Mapped[list] = mapped_column(JSONB, default=list)
    gaps: Mapped[list] = mapped_column(JSONB, default=list)
    uncertainties: Mapped[list] = mapped_column(JSONB, default=list)
    overall_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    summary: Mapped[str] = mapped_column(Text, default="")
    reasoning_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate: Mapped["Candidate"] = relationship(back_populates="reasonings")  # noqa: F821

    __table_args__ = (
        Index("ix_candidate_reasoning_candidate_job", "candidate_id", "job_id"),
    )


class HiringDecision(Base):
    """Recruiter-facing decision (mirrors shared HiringDecision)."""

    __tablename__ = "candidate_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )

    schema_version: Mapped[str] = mapped_column(String(10), default="1.0")
    recommendation: Mapped[str] = mapped_column(String(40))   # RecommendationLevel.value
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    derived_score: Mapped[float] = mapped_column(Float, default=0.0)
    reasons: Mapped[list] = mapped_column(JSONB, default=list)
    reservations: Mapped[list] = mapped_column(JSONB, default=list)
    interview_focus: Mapped[list] = mapped_column(JSONB, default=list)
    missing_evidence: Mapped[list] = mapped_column(JSONB, default=list)
    recommendations: Mapped[list] = mapped_column(JSONB, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    decision_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate: Mapped["Candidate"] = relationship(back_populates="decisions")  # noqa: F821

    __table_args__ = (
        Index("ix_candidate_decisions_candidate_job", "candidate_id", "job_id"),
    )
