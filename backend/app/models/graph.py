"""candidate_graphs / nodes / edges — persistence mirror of the shared CandidateGraph.

PK/id convention (Workstream A):
    * ``id`` (UUID) is the internal DB row PK on every table.
    * The shared *domain* id ``graph_id`` is a separate, unique String column.
    * Node/edge ``node_id`` / ``edge_id`` hold the shared canonical ids
      (e.g. 'skill:fastapi'); they are unique *within a graph*, so DB rows still get
      their own UUID surrogate PK.

Separate persistence mirror of ``app.shared.models.graph`` — never redefines the
shared Pydantic models. Nested/dict fields use JSONB; enums are stored as ``.value``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CandidateGraph(Base):
    """Parent row for one candidate's unified graph (mirrors shared CandidateGraph)."""

    __tablename__ = "candidate_graphs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    graph_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )

    schema_version: Mapped[str] = mapped_column(String(10), default="1.0")
    graph_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate: Mapped["Candidate"] = relationship(back_populates="graphs")  # noqa: F821
    nodes: Mapped[list["CandidateGraphNode"]] = relationship(
        back_populates="graph", cascade="all, delete-orphan"
    )
    edges: Mapped[list["CandidateGraphEdge"]] = relationship(
        back_populates="graph", cascade="all, delete-orphan"
    )


class CandidateGraphNode(Base):
    """A typed entity inside a candidate graph (mirrors shared GraphNode)."""

    __tablename__ = "candidate_graph_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    graph_pk: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_graphs.id", ondelete="CASCADE")
    )

    node_id: Mapped[str] = mapped_column(String(255))     # shared GraphNode.id (canonical)
    type: Mapped[str] = mapped_column(String(50))         # GraphNodeType.value
    label: Mapped[str] = mapped_column(String(512))
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    evidence_ids: Mapped[list] = mapped_column(JSONB, default=list)

    graph: Mapped["CandidateGraph"] = relationship(back_populates="nodes")

    __table_args__ = (
        UniqueConstraint("graph_pk", "node_id", name="uq_graph_node_id"),
        Index("ix_graph_nodes_graph_type", "graph_pk", "type"),
    )


class CandidateGraphEdge(Base):
    """A typed relationship between two nodes (mirrors shared GraphEdge)."""

    __tablename__ = "candidate_graph_edges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    graph_pk: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_graphs.id", ondelete="CASCADE")
    )

    edge_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # shared GraphEdge.id
    source_id: Mapped[str] = mapped_column(String(255))   # GraphNode.id (origin)
    target_id: Mapped[str] = mapped_column(String(255))   # GraphNode.id (destination)
    type: Mapped[str] = mapped_column(String(50))         # GraphEdgeType.value
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    evidence_ids: Mapped[list] = mapped_column(JSONB, default=list)

    graph: Mapped["CandidateGraph"] = relationship(back_populates="edges")

    __table_args__ = (
        Index("ix_graph_edges_graph_pk", "graph_pk"),
        Index("ix_graph_edges_source", "graph_pk", "source_id"),
        Index("ix_graph_edges_target", "graph_pk", "target_id"),
    )
