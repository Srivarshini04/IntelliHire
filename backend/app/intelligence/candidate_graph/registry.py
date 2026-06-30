"""GraphRegistry — store + query built CandidateGraphs for the Graph Query APIs.

This in-memory registry lets the FastAPI layer build a graph once and then answer
read queries (skills, projects, evidence, confidence, relationships) against it.
It is deliberately the *only* stateful piece and is trivially swappable: in
production the same interface is satisfied by the persistence repositories over
``app.models.graph`` / ``app.models.ledger`` (Postgres). Engines never touch it.

Process-local and not durable — fine for a single API worker / tests; replace with
the DB-backed repository when horizontal scale or durability is needed.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from app.shared.enums import GraphEdgeType, GraphNodeType
from app.shared.models.evidence import EvidenceLedgerEntry
from app.shared.models.graph import CandidateGraph, GraphEdge, GraphNode

logger = logging.getLogger(__name__)


class GraphRegistry:
    """Stores CandidateGraphs by id and exposes graph-intelligence read queries."""

    def __init__(self) -> None:
        self._by_id: dict[str, CandidateGraph] = {}
        self._latest_for_candidate: dict[str, str] = {}

    # --- writes --------------------------------------------------------------

    def put(self, graph: CandidateGraph) -> CandidateGraph:
        self._by_id[graph.graph_id] = graph
        self._latest_for_candidate[graph.candidate_id] = graph.graph_id
        logger.debug("registry.put graph_id=%s", graph.graph_id)
        return graph

    # --- graph lookup --------------------------------------------------------

    def get(self, graph_id: str) -> CandidateGraph | None:
        return self._by_id.get(graph_id)

    def latest_for_candidate(self, candidate_id: str) -> CandidateGraph | None:
        gid = self._latest_for_candidate.get(candidate_id)
        return self._by_id.get(gid) if gid else None

    # --- entity-level queries (operate on a resolved graph) ------------------

    def skills(self, graph: CandidateGraph) -> list[GraphNode]:
        nodes = graph.nodes_of_type(GraphNodeType.SKILL) + graph.nodes_of_type(
            GraphNodeType.TECHNOLOGY
        )
        return sorted(nodes, key=lambda n: n.confidence, reverse=True)

    def projects(self, graph: CandidateGraph) -> list[GraphNode]:
        return graph.nodes_of_type(GraphNodeType.PROJECT) + graph.nodes_of_type(
            GraphNodeType.REPOSITORY
        )

    def evidence_for_entity(
        self, graph: CandidateGraph, node_id: str
    ) -> list[EvidenceLedgerEntry]:
        return graph.evidence_for(node_id)

    def confidence_for(self, graph: CandidateGraph, node_id: str) -> float | None:
        node = graph.get_node(node_id)
        return node.confidence if node else None

    def relationships(
        self, graph: CandidateGraph, node_id: str | None = None
    ) -> list[GraphEdge]:
        if node_id is None:
            return list(graph.edges)
        return [e for e in graph.edges if e.source_id == node_id or e.target_id == node_id]

    def neighbors_by_edge(
        self, graph: CandidateGraph, node_id: str, edge_type: GraphEdgeType
    ) -> list[GraphNode]:
        target_ids = [
            e.target_id for e in graph.edges
            if e.source_id == node_id and e.type == edge_type
        ]
        return [n for n in graph.nodes if n.id in set(target_ids)]

    def find_nodes(
        self, graph: CandidateGraph, *, query: str, node_type: GraphNodeType | None = None
    ) -> list[GraphNode]:
        """Substring search over node labels/ids, optionally type-filtered."""
        q = query.strip().lower()
        out: list[GraphNode] = []
        for n in graph.nodes:
            if node_type and n.type != node_type:
                continue
            if q in n.label.lower() or q in n.id.lower():
                out.append(n)
        return out

    def summary(self, graph: CandidateGraph) -> dict:
        """Counts of nodes/edges by type — a compact graph overview."""
        node_counts: dict[str, int] = defaultdict(int)
        edge_counts: dict[str, int] = defaultdict(int)
        for n in graph.nodes:
            node_counts[n.type.value] += 1
        for e in graph.edges:
            edge_counts[e.type.value] += 1
        inferred = sum(1 for n in graph.nodes if n.attributes.get("inferred"))
        return {
            "graph_id": graph.graph_id,
            "candidate_id": graph.candidate_id,
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "evidence_count": len(graph.evidence_ledger),
            "inferred_node_count": inferred,
            "nodes_by_type": dict(node_counts),
            "edges_by_type": dict(edge_counts),
        }


# Process-local singleton used by the API routes.
graph_registry = GraphRegistry()
