"""Candidate Graph domain models — the shared knowledge representation.

Reasoning is graph traversal over this structure. The legacy
``candidate_graph.graph_schema.UnifiedCandidateGraph`` re-exports CandidateGraph
(field rename: entities->nodes, relationships->edges).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.shared.enums import GraphEdgeType, GraphNodeType
from app.shared.models.evidence import EvidenceLedgerEntry


class GraphNode(BaseModel):
    """A typed entity in the candidate graph (skill, project, org, ...)."""

    id: str = Field(..., description="Canonical id, e.g. 'skill:fastapi' or 'repo:clinicbot'.")
    type: GraphNodeType
    label: str = Field(..., description="Human display name.")
    attributes: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Fused confidence across all supporting evidence (set by FusionEngine).",
    )
    evidence_ids: list[str] = Field(
        default_factory=list, description="Evidence.evidence_id values supporting this node."
    )


class GraphEdge(BaseModel):
    """A typed relationship between two nodes."""

    id: str | None = None
    source_id: str = Field(..., description="GraphNode.id (origin).")
    target_id: str = Field(..., description="GraphNode.id (destination).")
    type: GraphEdgeType
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)


class CandidateGraph(BaseModel):
    """The unified, single-source representation of one candidate.

    Built by GraphBuilder from a list[Evidence]; node confidences fused by
    FusionEngine; consumed (read-only) by ReasoningEngine. No engine reads raw
    resumes/repos after this object exists.
    """

    schema_version: Literal["1.0"] = "1.0"
    graph_id: str = Field(..., description="Stable graph id, e.g. 'graph:c1:j1'.")
    candidate_id: str
    job_id: str | None = Field(
        default=None, description="Set when the graph is built/scoped for a specific role."
    )
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    evidence_ledger: list[EvidenceLedgerEntry] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # --- pure, side-effect-free traversal helpers ---

    def get_node(self, node_id: str) -> GraphNode | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    def nodes_of_type(self, node_type: GraphNodeType) -> list[GraphNode]:
        return [n for n in self.nodes if n.type == node_type]

    def evidence_for(self, node_id: str) -> list[EvidenceLedgerEntry]:
        return [e for e in self.evidence_ledger if e.supporting_node_id == node_id]
