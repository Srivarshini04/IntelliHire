"""EvidenceLedgerRepository — persistence for evidence_ledger rows."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger import EvidenceLedgerEntry as EvidenceLedgerORM
from app.repositories._util import enum_value, to_uuid
from app.shared.models.evidence import EvidenceLedgerEntry


class EvidenceLedgerRepository:
    """CRUD persistence for graph-bound evidence ledger entries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- mapping -----------------------------------------------------------

    @staticmethod
    def to_orm(entry: EvidenceLedgerEntry) -> EvidenceLedgerORM:
        return EvidenceLedgerORM(
            evidence_id=entry.evidence_id,
            candidate_id=to_uuid(entry.candidate_id),
            source=enum_value(entry.source),
            evidence_type=enum_value(entry.evidence_type),
            entity_ref=entry.entity_ref,
            claim=entry.claim,
            polarity=enum_value(entry.polarity),
            confidence=entry.confidence,
            supporting_node_id=entry.supporting_node_id,
            provenance=entry.provenance,
            verification_status=enum_value(entry.verification_status),
            timestamp=entry.timestamp,
        )

    @staticmethod
    def _apply(row: EvidenceLedgerORM, entry: EvidenceLedgerEntry) -> EvidenceLedgerORM:
        row.candidate_id = to_uuid(entry.candidate_id)
        row.source = enum_value(entry.source)
        row.evidence_type = enum_value(entry.evidence_type)
        row.entity_ref = entry.entity_ref
        row.claim = entry.claim
        row.polarity = enum_value(entry.polarity)
        row.confidence = entry.confidence
        row.supporting_node_id = entry.supporting_node_id
        row.provenance = entry.provenance
        row.verification_status = enum_value(entry.verification_status)
        row.timestamp = entry.timestamp
        return row

    @staticmethod
    def from_orm(row: EvidenceLedgerORM) -> EvidenceLedgerEntry:
        return EvidenceLedgerEntry(
            evidence_id=row.evidence_id,
            candidate_id=str(row.candidate_id),
            source=row.source,
            evidence_type=row.evidence_type,
            entity_ref=row.entity_ref,
            claim=row.claim,
            polarity=row.polarity,
            confidence=row.confidence,
            supporting_node_id=row.supporting_node_id,
            provenance=row.provenance or {},
            timestamp=row.timestamp,
            verification_status=row.verification_status,
        )

    # --- queries -----------------------------------------------------------

    async def create(self, entry: EvidenceLedgerEntry) -> EvidenceLedgerEntry:
        row = self.to_orm(entry)
        self.session.add(row)
        await self.session.flush()
        return self.from_orm(row)

    async def get_by_domain_id(self, evidence_id: str) -> EvidenceLedgerEntry | None:
        row = await self._row_by_domain_id(evidence_id)
        return self.from_orm(row) if row else None

    async def list_for_candidate(self, candidate_id: str) -> list[EvidenceLedgerEntry]:
        result = await self.session.execute(
            select(EvidenceLedgerORM).where(
                EvidenceLedgerORM.candidate_id == to_uuid(candidate_id)
            )
        )
        return [self.from_orm(r) for r in result.scalars().all()]

    async def list_for_job(self, job_id: str) -> list[EvidenceLedgerEntry]:
        # Evidence ledger entries are candidate-scoped, not job-scoped.
        return []

    async def upsert(self, entry: EvidenceLedgerEntry) -> EvidenceLedgerEntry:
        row = await self._row_by_domain_id(entry.evidence_id)
        if row is None:
            return await self.create(entry)
        self._apply(row, entry)
        await self.session.flush()
        return self.from_orm(row)

    async def _row_by_domain_id(self, evidence_id: str) -> EvidenceLedgerORM | None:
        result = await self.session.execute(
            select(EvidenceLedgerORM).where(EvidenceLedgerORM.evidence_id == evidence_id)
        )
        return result.scalar_one_or_none()
