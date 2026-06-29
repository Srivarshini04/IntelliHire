"""ReasoningRepository — persistence for candidate_reasoning rows."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reasoning import CandidateReasoning as CandidateReasoningORM
from app.repositories._util import to_uuid
from app.shared.models.reasoning import (
    CandidateGap,
    CandidateReasoning,
    ReasoningClaim,
)


class ReasoningRepository:
    """CRUD persistence for ReasoningEngine output."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- mapping -----------------------------------------------------------

    @staticmethod
    def to_orm(reasoning: CandidateReasoning) -> CandidateReasoningORM:
        return CandidateReasoningORM(
            reasoning_id=reasoning.reasoning_id,
            candidate_id=to_uuid(reasoning.candidate_id),
            job_id=to_uuid(reasoning.job_id),
            schema_version=reasoning.schema_version,
            claims=[c.model_dump(mode="json") for c in reasoning.claims],
            gaps=[g.model_dump(mode="json") for g in reasoning.gaps],
            uncertainties=list(reasoning.uncertainties),
            overall_confidence=reasoning.overall_confidence,
            summary=reasoning.summary,
            reasoning_metadata=reasoning.metadata,
        )

    @classmethod
    def _apply(cls, row: CandidateReasoningORM, reasoning: CandidateReasoning) -> CandidateReasoningORM:
        row.candidate_id = to_uuid(reasoning.candidate_id)
        row.job_id = to_uuid(reasoning.job_id)
        row.schema_version = reasoning.schema_version
        row.claims = [c.model_dump(mode="json") for c in reasoning.claims]
        row.gaps = [g.model_dump(mode="json") for g in reasoning.gaps]
        row.uncertainties = list(reasoning.uncertainties)
        row.overall_confidence = reasoning.overall_confidence
        row.summary = reasoning.summary
        row.reasoning_metadata = reasoning.metadata
        return row

    @staticmethod
    def from_orm(row: CandidateReasoningORM) -> CandidateReasoning:
        return CandidateReasoning(
            schema_version=row.schema_version,
            reasoning_id=row.reasoning_id,
            candidate_id=str(row.candidate_id),
            job_id=str(row.job_id),
            claims=[ReasoningClaim.model_validate(c) for c in (row.claims or [])],
            gaps=[CandidateGap.model_validate(g) for g in (row.gaps or [])],
            uncertainties=list(row.uncertainties or []),
            overall_confidence=row.overall_confidence,
            summary=row.summary or "",
            metadata=row.reasoning_metadata or {},
        )

    # --- queries -----------------------------------------------------------

    async def create(self, reasoning: CandidateReasoning) -> CandidateReasoning:
        row = self.to_orm(reasoning)
        self.session.add(row)
        await self.session.flush()
        return self.from_orm(row)

    async def get_by_domain_id(self, reasoning_id: str) -> CandidateReasoning | None:
        row = await self._row_by_domain_id(reasoning_id)
        return self.from_orm(row) if row else None

    async def list_for_candidate(self, candidate_id: str) -> list[CandidateReasoning]:
        result = await self.session.execute(
            select(CandidateReasoningORM).where(
                CandidateReasoningORM.candidate_id == to_uuid(candidate_id)
            )
        )
        return [self.from_orm(r) for r in result.scalars().all()]

    async def list_for_job(self, job_id: str) -> list[CandidateReasoning]:
        result = await self.session.execute(
            select(CandidateReasoningORM).where(
                CandidateReasoningORM.job_id == to_uuid(job_id)
            )
        )
        return [self.from_orm(r) for r in result.scalars().all()]

    async def upsert(self, reasoning: CandidateReasoning) -> CandidateReasoning:
        row = await self._row_by_domain_id(reasoning.reasoning_id)
        if row is None:
            return await self.create(reasoning)
        self._apply(row, reasoning)
        await self.session.flush()
        return self.from_orm(row)

    async def _row_by_domain_id(self, reasoning_id: str) -> CandidateReasoningORM | None:
        result = await self.session.execute(
            select(CandidateReasoningORM).where(
                CandidateReasoningORM.reasoning_id == reasoning_id
            )
        )
        return result.scalar_one_or_none()
