"""CandidateGraphRepository — persistence for candidate_graphs + nodes + edges."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.graph import (
    CandidateGraph as CandidateGraphORM,
    CandidateGraphEdge as CandidateGraphEdgeORM,
    CandidateGraphNode as CandidateGraphNodeORM,
)
from app.repositories._util import enum_value, to_uuid
from app.shared.models.graph import CandidateGraph, GraphEdge, GraphNode


class CandidateGraphRepository:
    """CRUD persistence for the candidate graph aggregate (parent + nodes + edges)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- mapping -----------------------------------------------------------

    @staticmethod
    def _node_to_orm(node: GraphNode) -> CandidateGraphNodeORM:
        return CandidateGraphNodeORM(
            node_id=node.id,
            type=enum_value(node.type),
            label=node.label,
            attributes=node.attributes,
            confidence=node.confidence,
            evidence_ids=node.evidence_ids,
        )

    @staticmethod
    def _edge_to_orm(edge: GraphEdge) -> CandidateGraphEdgeORM:
        return CandidateGraphEdgeORM(
            edge_id=edge.id,
            source_id=edge.source_id,
            target_id=edge.target_id,
            type=enum_value(edge.type),
            confidence=edge.confidence,
            evidence_ids=edge.evidence_ids,
        )

    @classmethod
    def to_orm(cls, graph: CandidateGraph) -> CandidateGraphORM:
        row = CandidateGraphORM(
            graph_id=graph.graph_id,
            candidate_id=to_uuid(graph.candidate_id),
            job_id=to_uuid(graph.job_id) if graph.job_id else None,
            schema_version=graph.schema_version,
            graph_metadata=graph.metadata,
        )
        row.nodes = [cls._node_to_orm(n) for n in graph.nodes]
        row.edges = [cls._edge_to_orm(e) for e in graph.edges]
        return row

    @classmethod
    def from_orm(cls, row: CandidateGraphORM) -> CandidateGraph:
        return CandidateGraph(
            schema_version=row.schema_version,
            graph_id=row.graph_id,
            candidate_id=str(row.candidate_id),
            job_id=str(row.job_id) if row.job_id else None,
            nodes=[
                GraphNode(
                    id=n.node_id,
                    type=n.type,
                    label=n.label,
                    attributes=n.attributes or {},
                    confidence=n.confidence,
                    evidence_ids=n.evidence_ids or [],
                )
                for n in row.nodes
            ],
            edges=[
                GraphEdge(
                    id=e.edge_id,
                    source_id=e.source_id,
                    target_id=e.target_id,
                    type=e.type,
                    confidence=e.confidence,
                    evidence_ids=e.evidence_ids or [],
                )
                for e in row.edges
            ],
            # evidence_ledger lives in its own table (EvidenceLedgerRepository).
            metadata=row.graph_metadata or {},
        )

    # --- queries -----------------------------------------------------------

    async def create(self, graph: CandidateGraph) -> CandidateGraph:
        row = self.to_orm(graph)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row, ["nodes", "edges"])
        return self.from_orm(row)

    async def get_by_domain_id(self, graph_id: str) -> CandidateGraph | None:
        row = await self._row_by_domain_id(graph_id)
        return self.from_orm(row) if row else None

    async def list_for_candidate(self, candidate_id: str) -> list[CandidateGraph]:
        result = await self.session.execute(
            select(CandidateGraphORM)
            .where(CandidateGraphORM.candidate_id == to_uuid(candidate_id))
            .options(
                selectinload(CandidateGraphORM.nodes),
                selectinload(CandidateGraphORM.edges),
            )
        )
        return [self.from_orm(r) for r in result.scalars().all()]

    async def list_for_job(self, job_id: str) -> list[CandidateGraph]:
        result = await self.session.execute(
            select(CandidateGraphORM)
            .where(CandidateGraphORM.job_id == to_uuid(job_id))
            .options(
                selectinload(CandidateGraphORM.nodes),
                selectinload(CandidateGraphORM.edges),
            )
        )
        return [self.from_orm(r) for r in result.scalars().all()]

    async def upsert(self, graph: CandidateGraph) -> CandidateGraph:
        row = await self._row_by_domain_id(graph.graph_id)
        if row is None:
            return await self.create(graph)
        row.candidate_id = to_uuid(graph.candidate_id)
        row.job_id = to_uuid(graph.job_id) if graph.job_id else None
        row.schema_version = graph.schema_version
        row.graph_metadata = graph.metadata
        # Replace child collections wholesale (cascade delete-orphan removes old rows).
        row.nodes = [self._node_to_orm(n) for n in graph.nodes]
        row.edges = [self._edge_to_orm(e) for e in graph.edges]
        await self.session.flush()
        await self.session.refresh(row, ["nodes", "edges"])
        return self.from_orm(row)

    async def _row_by_domain_id(self, graph_id: str) -> CandidateGraphORM | None:
        result = await self.session.execute(
            select(CandidateGraphORM)
            .where(CandidateGraphORM.graph_id == graph_id)
            .options(
                selectinload(CandidateGraphORM.nodes),
                selectinload(CandidateGraphORM.edges),
            )
        )
        return result.scalar_one_or_none()
