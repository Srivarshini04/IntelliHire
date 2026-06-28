"""DecisionRepository — persistence for candidate_decisions rows."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reasoning import HiringDecision as HiringDecisionORM
from app.repositories._util import enum_value, to_uuid
from app.shared.models.reasoning import (
    HiringDecision,
    InterviewFocus,
    Recommendation,
)


class DecisionRepository:
    """CRUD persistence for DecisionEngine output (HiringDecision)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- mapping -----------------------------------------------------------

    @staticmethod
    def to_orm(decision: HiringDecision) -> HiringDecisionORM:
        return HiringDecisionORM(
            decision_id=decision.decision_id,
            candidate_id=to_uuid(decision.candidate_id),
            job_id=to_uuid(decision.job_id),
            schema_version=decision.schema_version,
            recommendation=enum_value(decision.recommendation),
            confidence=decision.confidence,
            derived_score=decision.derived_score,
            reasons=list(decision.reasons),
            reservations=list(decision.reservations),
            interview_focus=[f.model_dump(mode="json") for f in decision.interview_focus],
            missing_evidence=list(decision.missing_evidence),
            recommendations=[r.model_dump(mode="json") for r in decision.recommendations],
            summary=decision.summary,
            decision_metadata=decision.metadata,
            decided_at=decision.decided_at,
        )

    @classmethod
    def _apply(cls, row: HiringDecisionORM, decision: HiringDecision) -> HiringDecisionORM:
        row.candidate_id = to_uuid(decision.candidate_id)
        row.job_id = to_uuid(decision.job_id)
        row.schema_version = decision.schema_version
        row.recommendation = enum_value(decision.recommendation)
        row.confidence = decision.confidence
        row.derived_score = decision.derived_score
        row.reasons = list(decision.reasons)
        row.reservations = list(decision.reservations)
        row.interview_focus = [f.model_dump(mode="json") for f in decision.interview_focus]
        row.missing_evidence = list(decision.missing_evidence)
        row.recommendations = [r.model_dump(mode="json") for r in decision.recommendations]
        row.summary = decision.summary
        row.decision_metadata = decision.metadata
        row.decided_at = decision.decided_at
        return row

    @staticmethod
    def from_orm(row: HiringDecisionORM) -> HiringDecision:
        return HiringDecision(
            schema_version=row.schema_version,
            decision_id=row.decision_id,
            candidate_id=str(row.candidate_id),
            job_id=str(row.job_id),
            recommendation=row.recommendation,
            confidence=row.confidence,
            derived_score=row.derived_score,
            reasons=list(row.reasons or []),
            reservations=list(row.reservations or []),
            interview_focus=[InterviewFocus.model_validate(f) for f in (row.interview_focus or [])],
            missing_evidence=list(row.missing_evidence or []),
            recommendations=[Recommendation.model_validate(r) for r in (row.recommendations or [])],
            summary=row.summary or "",
            decided_at=row.decided_at,
            metadata=row.decision_metadata or {},
        )

    # --- queries -----------------------------------------------------------

    async def create(self, decision: HiringDecision) -> HiringDecision:
        row = self.to_orm(decision)
        self.session.add(row)
        await self.session.flush()
        return self.from_orm(row)

    async def get_by_domain_id(self, decision_id: str) -> HiringDecision | None:
        row = await self._row_by_domain_id(decision_id)
        return self.from_orm(row) if row else None

    async def list_for_candidate(self, candidate_id: str) -> list[HiringDecision]:
        result = await self.session.execute(
            select(HiringDecisionORM).where(
                HiringDecisionORM.candidate_id == to_uuid(candidate_id)
            )
        )
        return [self.from_orm(r) for r in result.scalars().all()]

    async def list_for_job(self, job_id: str) -> list[HiringDecision]:
        result = await self.session.execute(
            select(HiringDecisionORM).where(HiringDecisionORM.job_id == to_uuid(job_id))
        )
        return [self.from_orm(r) for r in result.scalars().all()]

    async def upsert(self, decision: HiringDecision) -> HiringDecision:
        row = await self._row_by_domain_id(decision.decision_id)
        if row is None:
            return await self.create(decision)
        self._apply(row, decision)
        await self.session.flush()
        return self.from_orm(row)

    async def _row_by_domain_id(self, decision_id: str) -> HiringDecisionORM | None:
        result = await self.session.execute(
            select(HiringDecisionORM).where(HiringDecisionORM.decision_id == decision_id)
        )
        return result.scalar_one_or_none()
