from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CapabilityProfile(Base):
    __tablename__ = "capability_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("candidates.id"), unique=True)
    technical: Mapped[float] = mapped_column(Float, default=0.0)
    execution: Mapped[float] = mapped_column(Float, default=0.0)
    ownership: Mapped[float] = mapped_column(Float, default=0.0)
    learning_velocity: Mapped[float] = mapped_column(Float, default=0.0)
    problem_solving: Mapped[float] = mapped_column(Float, default=0.0)
    domain_expertise: Mapped[float] = mapped_column(Float, default=0.0)
    capability_score: Mapped[float] = mapped_column(Float, default=0.0)

    candidate: Mapped["Candidate"] = relationship(back_populates="capability_profile")


class RiskProfile(Base):
    __tablename__ = "risk_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("candidates.id"), unique=True)
    evidence_risk: Mapped[float] = mapped_column(Float, default=0.0)
    role_gap_risk: Mapped[float] = mapped_column(Float, default=0.0)
    credibility_risk: Mapped[float] = mapped_column(Float, default=0.0)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)

    candidate: Mapped["Candidate"] = relationship(back_populates="risk_profile")


class HiddenTalentProfile(Base):
    __tablename__ = "hidden_talent_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("candidates.id"), unique=True)
    visibility_score: Mapped[float] = mapped_column(Float, default=0.0)
    hti_score: Mapped[float] = mapped_column(Float, default=0.0)

    candidate: Mapped["Candidate"] = relationship(back_populates="hidden_talent_profile")


class Ranking(Base):
    __tablename__ = "rankings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"))
    candidate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("candidates.id"), unique=True)
    fit_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(String(50), nullable=True)

    job: Mapped["Job"] = relationship(back_populates="rankings")
    candidate: Mapped["Candidate"] = relationship(back_populates="ranking")
