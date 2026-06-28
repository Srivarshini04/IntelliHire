"""RankingRepository — persistence for candidate_rankings rows."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ranking import CandidateRanking as CandidateRankingORM
from app.repositories._util import enum_value, to_uuid
from app.shared.models.ranking import CandidateRanking


class RankingRepository:
    """CRUD persistence for ranked candidate rows (retrieval + rerank stages)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- mapping -----------------------------------------------------------

    @staticmethod
    def to_orm(ranking: CandidateRanking) -> CandidateRankingORM:
        return CandidateRankingORM(
            ranking_id=ranking.ranking_id,
            job_id=to_uuid(ranking.job_id),
            candidate_id=to_uuid(ranking.candidate_id),
            rank=ranking.rank,
            score=ranking.score,
            stage=enum_value(ranking.stage),
            reasoning=ranking.reasoning,
            decision_ref=ranking.decision_ref,
            ranking_metadata=ranking.metadata,
        )

    @staticmethod
    def _apply(row: CandidateRankingORM, ranking: CandidateRanking) -> CandidateRankingORM:
        row.job_id = to_uuid(ranking.job_id)
        row.candidate_id = to_uuid(ranking.candidate_id)
        row.rank = ranking.rank
        row.score = ranking.score
        row.stage = enum_value(ranking.stage)
        row.reasoning = ranking.reasoning
        row.decision_ref = ranking.decision_ref
        row.ranking_metadata = ranking.metadata
        return row

    @staticmethod
    def from_orm(row: CandidateRankingORM) -> CandidateRanking:
        return CandidateRanking(
            ranking_id=row.ranking_id,
            job_id=str(row.job_id),
            candidate_id=str(row.candidate_id),
            rank=row.rank,
            score=row.score,
            stage=row.stage,
            reasoning=row.reasoning or "",
            decision_ref=row.decision_ref,
            metadata=row.ranking_metadata or {},
        )

    # --- queries -----------------------------------------------------------

    async def create(self, ranking: CandidateRanking) -> CandidateRanking:
        row = self.to_orm(ranking)
        self.session.add(row)
        await self.session.flush()
        return self.from_orm(row)

    async def get_by_domain_id(self, ranking_id: str) -> CandidateRanking | None:
        row = await self._row_by_domain_id(ranking_id)
        return self.from_orm(row) if row else None

    async def list_for_candidate(self, candidate_id: str) -> list[CandidateRanking]:
        result = await self.session.execute(
            select(CandidateRankingORM)
            .where(CandidateRankingORM.candidate_id == to_uuid(candidate_id))
            .order_by(CandidateRankingORM.rank)
        )
        return [self.from_orm(r) for r in result.scalars().all()]

    async def list_for_job(self, job_id: str) -> list[CandidateRanking]:
        result = await self.session.execute(
            select(CandidateRankingORM)
            .where(CandidateRankingORM.job_id == to_uuid(job_id))
            .order_by(CandidateRankingORM.rank)
        )
        return [self.from_orm(r) for r in result.scalars().all()]

    async def upsert(self, ranking: CandidateRanking) -> CandidateRanking:
        # Upsert keyed on the natural (job, candidate, stage) unique constraint so a
        # re-rank of the same candidate replaces its prior row for that stage.
        row = await self._row_by_natural_key(
            to_uuid(ranking.job_id), to_uuid(ranking.candidate_id), enum_value(ranking.stage)
        )
        if row is None:
            return await self.create(ranking)
        self._apply(row, ranking)
        await self.session.flush()
        return self.from_orm(row)

    async def _row_by_domain_id(self, ranking_id: str) -> CandidateRankingORM | None:
        result = await self.session.execute(
            select(CandidateRankingORM).where(CandidateRankingORM.ranking_id == ranking_id)
        )
        return result.scalar_one_or_none()

    async def _row_by_natural_key(self, job_id, candidate_id, stage) -> CandidateRankingORM | None:
        result = await self.session.execute(
            select(CandidateRankingORM).where(
                CandidateRankingORM.job_id == job_id,
                CandidateRankingORM.candidate_id == candidate_id,
                CandidateRankingORM.stage == stage,
            )
        )
        return result.scalar_one_or_none()
