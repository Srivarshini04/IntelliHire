"""candidate_rankings — persistence mirror of the shared CandidateRanking.

PK/id convention (Workstream A):
    * ``id`` (UUID) is the internal DB row PK.
    * The shared *domain* id ``ranking_id`` is a separate, unique String column.

Separate persistence mirror of ``app.shared.models.ranking.CandidateRanking`` — never
redefines the shared Pydantic model. ``stage`` stores RankingStage.value; ``metadata``
is JSONB.

NOTE: this is a NEW v2 table, distinct from the legacy ``rankings`` table
(``app.models.scoring.Ranking``); both coexist.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CandidateRanking(Base):
    """One ranked candidate for one job at one funnel stage (mirrors CandidateRanking)."""

    __tablename__ = "candidate_rankings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ranking_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )

    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    stage: Mapped[str] = mapped_column(String(20))   # RankingStage.value
    reasoning: Mapped[str] = mapped_column(Text, default="")
    decision_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ranking_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped["Job"] = relationship(back_populates="v2_rankings")  # noqa: F821
    candidate: Mapped["Candidate"] = relationship(back_populates="v2_rankings")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("job_id", "candidate_id", "stage", name="uq_ranking_job_candidate_stage"),
        Index("ix_candidate_rankings_job_rank", "job_id", "rank"),
    )
