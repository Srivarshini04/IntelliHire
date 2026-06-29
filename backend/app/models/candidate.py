from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"))
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    leetcode_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    resume_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped["Job"] = relationship(back_populates="candidates")
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="candidate")
    capability_profile: Mapped["CapabilityProfile | None"] = relationship(back_populates="candidate")
    risk_profile: Mapped["RiskProfile | None"] = relationship(back_populates="candidate")
    hidden_talent_profile: Mapped["HiddenTalentProfile | None"] = relationship(back_populates="candidate")
    ranking: Mapped["Ranking | None"] = relationship(back_populates="candidate")

    # --- DELULU v2 persistence (back-references; cascade lives on the v2 side) ---
    ledger_entries: Mapped[list["EvidenceLedgerEntry"]] = relationship(back_populates="candidate")  # noqa: F821
    graphs: Mapped[list["CandidateGraph"]] = relationship(back_populates="candidate")  # noqa: F821
    reasonings: Mapped[list["CandidateReasoning"]] = relationship(back_populates="candidate")  # noqa: F821
    decisions: Mapped[list["HiringDecision"]] = relationship(back_populates="candidate")  # noqa: F821
    v2_rankings: Mapped[list["CandidateRanking"]] = relationship(back_populates="candidate")  # noqa: F821
