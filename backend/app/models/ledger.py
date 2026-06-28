"""evidence_ledger — persistence mirror of shared EvidenceLedgerEntry.

PK/id convention (Workstream A):
    * ``id`` is the internal DB row PK (UUID), consistent with every other table.
    * The shared *domain* id (here ``evidence_id``) is stored as a separate, unique
      String column so repositories can look rows up by the stable id the rest of the
      system uses, while the DB keeps a uniform UUID surrogate key.

This ORM is a *separate* persistence mirror of
``app.shared.models.evidence.EvidenceLedgerEntry`` — it never redefines or imports
the shared Pydantic model into the table. Enums are stored as their ``.value``
strings.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EvidenceLedgerEntry(Base):
    """Graph-bound evidence row (mirrors shared EvidenceLedgerEntry)."""

    __tablename__ = "evidence_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Stable shared-domain id.
    evidence_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE")
    )

    source: Mapped[str] = mapped_column(String(50))           # EvidenceSource.value
    evidence_type: Mapped[str] = mapped_column(String(50))    # EvidenceType.value
    entity_ref: Mapped[str] = mapped_column(String(255))
    claim: Mapped[str] = mapped_column(Text)
    polarity: Mapped[str] = mapped_column(String(20), default="supports")  # EvidencePolarity.value
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    supporting_node_id: Mapped[str] = mapped_column(String(255))
    provenance: Mapped[dict] = mapped_column(JSONB, default=dict)
    verification_status: Mapped[str] = mapped_column(String(30), default="unverified")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate: Mapped["Candidate"] = relationship(back_populates="ledger_entries")  # noqa: F821

    __table_args__ = (
        Index("ix_evidence_ledger_candidate_id", "candidate_id"),
        Index("ix_evidence_ledger_supporting_node_id", "supporting_node_id"),
        Index("ix_evidence_ledger_entity_ref", "entity_ref"),
    )
