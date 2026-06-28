"""DELULU v2 persistence tables

Creates the Workstream A v2 tables (evidence_ledger, candidate_graphs + nodes +
edges, candidate_reasoning, candidate_decisions, candidate_rankings) and their FKs
to the pre-existing ``candidates`` / ``jobs`` tables. Those parent tables, and the
other legacy tables, are assumed to already exist (they are managed by
``Base.metadata.create_all`` in ``app.core.database.init_db``); this revision adds
only the new v2 surface.

Revision ID: 0001_v2_persistence
Revises:
Create Date: 2026-06-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_v2_persistence"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- evidence_ledger -------------------------------------------------
    op.create_table(
        "evidence_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("evidence_id", sa.String(length=255), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("evidence_type", sa.String(length=50), nullable=False),
        sa.Column("entity_ref", sa.String(length=255), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("polarity", sa.String(length=20), nullable=False, server_default="supports"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("supporting_node_id", sa.String(length=255), nullable=False),
        sa.Column("provenance", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("verification_status", sa.String(length=30), nullable=False, server_default="unverified"),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("evidence_id", name="uq_evidence_ledger_evidence_id"),
    )
    op.create_index("ix_evidence_ledger_evidence_id", "evidence_ledger", ["evidence_id"], unique=True)
    op.create_index("ix_evidence_ledger_candidate_id", "evidence_ledger", ["candidate_id"])
    op.create_index("ix_evidence_ledger_supporting_node_id", "evidence_ledger", ["supporting_node_id"])
    op.create_index("ix_evidence_ledger_entity_ref", "evidence_ledger", ["entity_ref"])

    # --- candidate_graphs ------------------------------------------------
    op.create_table(
        "candidate_graphs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("graph_id", sa.String(length=255), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("schema_version", sa.String(length=10), nullable=False, server_default="1.0"),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("graph_id", name="uq_candidate_graphs_graph_id"),
    )
    op.create_index("ix_candidate_graphs_graph_id", "candidate_graphs", ["graph_id"], unique=True)
    op.create_index("ix_candidate_graphs_candidate_id", "candidate_graphs", ["candidate_id"])
    op.create_index("ix_candidate_graphs_job_id", "candidate_graphs", ["job_id"])

    # --- candidate_graph_nodes ------------------------------------------
    op.create_table(
        "candidate_graph_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("graph_pk", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("node_id", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=512), nullable=False),
        sa.Column("attributes", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
        sa.Column("evidence_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.ForeignKeyConstraint(["graph_pk"], ["candidate_graphs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("graph_pk", "node_id", name="uq_graph_node_id"),
    )
    op.create_index("ix_graph_nodes_graph_type", "candidate_graph_nodes", ["graph_pk", "type"])

    # --- candidate_graph_edges ------------------------------------------
    op.create_table(
        "candidate_graph_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("graph_pk", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("edge_id", sa.String(length=255), nullable=True),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
        sa.Column("evidence_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.ForeignKeyConstraint(["graph_pk"], ["candidate_graphs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_graph_edges_graph_pk", "candidate_graph_edges", ["graph_pk"])
    op.create_index("ix_graph_edges_source", "candidate_graph_edges", ["graph_pk", "source_id"])
    op.create_index("ix_graph_edges_target", "candidate_graph_edges", ["graph_pk", "target_id"])

    # --- candidate_reasoning --------------------------------------------
    op.create_table(
        "candidate_reasoning",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("reasoning_id", sa.String(length=255), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.String(length=10), nullable=False, server_default="1.0"),
        sa.Column("claims", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("gaps", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("uncertainties", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("overall_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("reasoning_id", name="uq_candidate_reasoning_reasoning_id"),
    )
    op.create_index("ix_candidate_reasoning_reasoning_id", "candidate_reasoning", ["reasoning_id"], unique=True)
    op.create_index("ix_candidate_reasoning_candidate_id", "candidate_reasoning", ["candidate_id"])
    op.create_index("ix_candidate_reasoning_job_id", "candidate_reasoning", ["job_id"])
    op.create_index("ix_candidate_reasoning_candidate_job", "candidate_reasoning", ["candidate_id", "job_id"])

    # --- candidate_decisions --------------------------------------------
    op.create_table(
        "candidate_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("decision_id", sa.String(length=255), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.String(length=10), nullable=False, server_default="1.0"),
        sa.Column("recommendation", sa.String(length=40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("derived_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("reasons", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("reservations", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("interview_focus", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("missing_evidence", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("recommendations", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("decision_id", name="uq_candidate_decisions_decision_id"),
    )
    op.create_index("ix_candidate_decisions_decision_id", "candidate_decisions", ["decision_id"], unique=True)
    op.create_index("ix_candidate_decisions_candidate_id", "candidate_decisions", ["candidate_id"])
    op.create_index("ix_candidate_decisions_job_id", "candidate_decisions", ["job_id"])
    op.create_index("ix_candidate_decisions_candidate_job", "candidate_decisions", ["candidate_id", "job_id"])

    # --- candidate_rankings ---------------------------------------------
    op.create_table(
        "candidate_rankings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ranking_id", sa.String(length=255), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("stage", sa.String(length=20), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False, server_default=""),
        sa.Column("decision_ref", sa.String(length=255), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("ranking_id", name="uq_candidate_rankings_ranking_id"),
        sa.UniqueConstraint("job_id", "candidate_id", "stage", name="uq_ranking_job_candidate_stage"),
    )
    op.create_index("ix_candidate_rankings_ranking_id", "candidate_rankings", ["ranking_id"], unique=True)
    op.create_index("ix_candidate_rankings_job_id", "candidate_rankings", ["job_id"])
    op.create_index("ix_candidate_rankings_candidate_id", "candidate_rankings", ["candidate_id"])
    op.create_index("ix_candidate_rankings_job_rank", "candidate_rankings", ["job_id", "rank"])


def downgrade() -> None:
    op.drop_table("candidate_rankings")
    op.drop_table("candidate_decisions")
    op.drop_table("candidate_reasoning")
    op.drop_table("candidate_graph_edges")
    op.drop_table("candidate_graph_nodes")
    op.drop_table("candidate_graphs")
    op.drop_table("evidence_ledger")
