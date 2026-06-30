"""Candidate Intelligence Graph store — NetworkX backend, pluggable for Neo4j.

The store is the mutable working surface the GraphBuilder writes into. It is kept
deliberately separate from the *frozen* shared ``CandidateGraph`` Pydantic model:

    raw Evidence --(GraphBuilder)--> GraphStore (mutable, NetworkX)
                                         |  .to_candidate_graph()
                                         v
                                   CandidateGraph (frozen, shared, API/DB)

A ``GraphStoreBackend`` Protocol defines the minimal surface every backend must
provide, so a ``Neo4jGraphStore`` can be dropped in later without touching the
engines. ``NetworkXGraphStore`` is the default in-process implementation.

Edges are stored in a ``MultiDiGraph`` keyed by ``edge_type`` — this allows
several *different* relationship types between the same pair of nodes (e.g. a repo
can both ``PROVES`` a skill and ``USES`` a technology) while collapsing duplicate
*same-type* edges into one (with merged evidence).
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Protocol, runtime_checkable

import networkx as nx

from app.shared.enums import GraphEdgeType, GraphNodeType
from app.shared.models.evidence import EvidenceLedgerEntry
from app.shared.models.graph import CandidateGraph, GraphEdge, GraphNode

logger = logging.getLogger(__name__)


@runtime_checkable
class GraphStoreBackend(Protocol):
    """Minimal backend contract — implement this to plug in Neo4j/Memgraph/etc."""

    def add_node(
        self,
        node_id: str,
        node_type: GraphNodeType,
        label: str,
        *,
        confidence: float = 1.0,
        evidence_ids: Iterable[str] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None: ...

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: GraphEdgeType,
        *,
        confidence: float = 1.0,
        evidence_ids: Iterable[str] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None: ...

    def has_node(self, node_id: str) -> bool: ...

    def neighbors(self, node_id: str, edge_type: GraphEdgeType | None = None) -> list[str]: ...

    def to_candidate_graph(
        self, ledger_entries: Iterable[EvidenceLedgerEntry] | None = None
    ) -> CandidateGraph: ...


class NetworkXGraphStore:
    """In-process candidate graph backed by ``networkx.MultiDiGraph``."""

    def __init__(self, graph_id: str, candidate_id: str, job_id: str | None = None) -> None:
        self.graph_id = graph_id
        self.candidate_id = candidate_id
        self.job_id = job_id
        self._g: nx.MultiDiGraph = nx.MultiDiGraph()
        self.metadata: dict[str, Any] = {}

    # --- node operations (dynamic creation) ----------------------------------

    def add_node(
        self,
        node_id: str,
        node_type: GraphNodeType,
        label: str,
        *,
        confidence: float = 1.0,
        evidence_ids: Iterable[str] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Create a node, or merge into an existing one (union of evidence_ids).

        Idempotent on ``node_id``: re-adding the same id keeps the first type/label
        but unions evidence and merges attributes. This is what lets every Evidence
        about ``skill:python`` collapse onto a single node.
        """
        ev_ids = list(evidence_ids or [])
        attrs = dict(attributes or {})

        if self._g.has_node(node_id):
            data = self._g.nodes[node_id]
            data["evidence_ids"] = _union(data.get("evidence_ids", []), ev_ids)
            data["attributes"] = {**data.get("attributes", {}), **attrs}
            # Keep the highest seen base confidence until the fusion engine runs.
            data["confidence"] = max(data.get("confidence", 0.0), confidence)
            return

        self._g.add_node(
            node_id,
            type=node_type,
            label=label,
            confidence=confidence,
            evidence_ids=ev_ids,
            attributes=attrs,
        )
        logger.debug("graph.add_node id=%s type=%s", node_id, node_type.value)

    def has_node(self, node_id: str) -> bool:
        return self._g.has_node(node_id)

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        if not self._g.has_node(node_id):
            return None
        return {"id": node_id, **self._g.nodes[node_id]}

    def node_ids(self) -> list[str]:
        return list(self._g.nodes)

    def nodes_of_type(self, node_type: GraphNodeType) -> list[str]:
        return [n for n, d in self._g.nodes(data=True) if d.get("type") == node_type]

    def set_node_confidence(self, node_id: str, confidence: float) -> None:
        if self._g.has_node(node_id):
            self._g.nodes[node_id]["confidence"] = confidence

    def update_node_attributes(self, node_id: str, **attrs: Any) -> None:
        if self._g.has_node(node_id):
            self._g.nodes[node_id].setdefault("attributes", {}).update(attrs)

    # --- edge operations (dynamic creation) ----------------------------------

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: GraphEdgeType,
        *,
        confidence: float = 1.0,
        evidence_ids: Iterable[str] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Create a typed, evidence-bearing edge (idempotent per (src,tgt,type)).

        Missing endpoints are created as bare nodes so inference can attach edges
        before/independently of node creation; callers normally add nodes first.
        """
        for nid in (source_id, target_id):
            if not self._g.has_node(nid):
                logger.debug("graph.add_edge auto-creating bare node id=%s", nid)
                self._g.add_node(
                    nid, type=GraphNodeType.SKILL, label=nid, confidence=confidence,
                    evidence_ids=[], attributes={"auto_created": True},
                )

        key = edge_type.value
        ev_ids = list(evidence_ids or [])
        attrs = dict(attributes or {})

        if self._g.has_edge(source_id, target_id, key):
            data = self._g.edges[source_id, target_id, key]
            data["evidence_ids"] = _union(data.get("evidence_ids", []), ev_ids)
            data["attributes"] = {**data.get("attributes", {}), **attrs}
            data["confidence"] = max(data.get("confidence", 0.0), confidence)
            return

        self._g.add_edge(
            source_id, target_id, key=key,
            type=edge_type, confidence=confidence, evidence_ids=ev_ids, attributes=attrs,
        )
        logger.debug("graph.add_edge %s -[%s]-> %s", source_id, key, target_id)

    def has_edge(self, source_id: str, target_id: str, edge_type: GraphEdgeType) -> bool:
        return self._g.has_edge(source_id, target_id, edge_type.value)

    def set_edge_confidence(
        self, source_id: str, target_id: str, edge_type: GraphEdgeType, confidence: float
    ) -> None:
        if self._g.has_edge(source_id, target_id, edge_type.value):
            self._g.edges[source_id, target_id, edge_type.value]["confidence"] = confidence

    def edges(self) -> list[tuple[str, str, str, dict[str, Any]]]:
        """``(source, target, edge_type_value, data)`` for every edge."""
        return [(u, v, k, d) for u, v, k, d in self._g.edges(keys=True, data=True)]

    # --- traversal -----------------------------------------------------------

    def neighbors(self, node_id: str, edge_type: GraphEdgeType | None = None) -> list[str]:
        """Outbound neighbours of ``node_id``, optionally filtered by edge type."""
        if not self._g.has_node(node_id):
            return []
        out: list[str] = []
        for _, tgt, k in self._g.out_edges(node_id, keys=True):
            if edge_type is None or k == edge_type.value:
                if tgt not in out:
                    out.append(tgt)
        return out

    def traverse(
        self, start_id: str, *, max_depth: int = 2, edge_types: set[GraphEdgeType] | None = None
    ) -> list[str]:
        """Breadth-first reachable nodes from ``start_id`` up to ``max_depth`` hops."""
        if not self._g.has_node(start_id):
            return []
        allowed = {e.value for e in edge_types} if edge_types else None
        seen: set[str] = {start_id}
        order: list[str] = []
        frontier = [(start_id, 0)]
        while frontier:
            node, depth = frontier.pop(0)
            if depth >= max_depth:
                continue
            for _, tgt, k in self._g.out_edges(node, keys=True):
                if allowed is not None and k not in allowed:
                    continue
                if tgt not in seen:
                    seen.add(tgt)
                    order.append(tgt)
                    frontier.append((tgt, depth + 1))
        return order

    def subgraph_for(self, node_id: str, *, max_depth: int = 2) -> list[str]:
        """The node plus everything reachable within ``max_depth`` (inclusive)."""
        return [node_id, *self.traverse(node_id, max_depth=max_depth)]

    # --- node merging (used by the duplicate-detection engine) ---------------

    def merge_nodes(self, keep_id: str, drop_id: str) -> None:
        """Collapse ``drop_id`` into ``keep_id``, preserving all evidence + edges.

        Evidence ids are unioned, attributes merged, and every edge touching
        ``drop_id`` is rewired to ``keep_id`` (self-loops dropped). This is how the
        DuplicateDetector guarantees "preserve evidence links after merge".
        """
        if keep_id == drop_id or not self._g.has_node(drop_id):
            return
        if not self._g.has_node(keep_id):
            nx.relabel_nodes(self._g, {drop_id: keep_id}, copy=False)
            return

        keep, drop = self._g.nodes[keep_id], self._g.nodes[drop_id]
        keep["evidence_ids"] = _union(keep.get("evidence_ids", []), drop.get("evidence_ids", []))
        keep["attributes"] = {**drop.get("attributes", {}), **keep.get("attributes", {})}
        keep.setdefault("attributes", {}).setdefault("merged_aliases", []).append(drop_id)
        keep["confidence"] = max(keep.get("confidence", 0.0), drop.get("confidence", 0.0))

        for _, tgt, k, d in list(self._g.out_edges(drop_id, keys=True, data=True)):
            if tgt != keep_id:
                self.add_edge(keep_id, tgt, d["type"], confidence=d["confidence"],
                              evidence_ids=d.get("evidence_ids"), attributes=d.get("attributes"))
        for src, _, k, d in list(self._g.in_edges(drop_id, keys=True, data=True)):
            if src != keep_id:
                self.add_edge(src, keep_id, d["type"], confidence=d["confidence"],
                              evidence_ids=d.get("evidence_ids"), attributes=d.get("attributes"))

        self._g.remove_node(drop_id)
        logger.info("graph.merge_nodes kept=%s dropped=%s", keep_id, drop_id)

    # --- export / import -----------------------------------------------------

    def to_candidate_graph(
        self, ledger_entries: Iterable[EvidenceLedgerEntry] | None = None
    ) -> CandidateGraph:
        """Export to the frozen shared ``CandidateGraph`` (the API/DB contract)."""
        nodes = [
            GraphNode(
                id=n,
                type=d["type"],
                label=d.get("label", n),
                confidence=round(float(d.get("confidence", 1.0)), 4),
                evidence_ids=list(d.get("evidence_ids", [])),
                attributes=dict(d.get("attributes", {})),
            )
            for n, d in self._g.nodes(data=True)
        ]
        edges = [
            GraphEdge(
                id=f"{u}|{k}|{v}",
                source_id=u,
                target_id=v,
                type=d["type"],
                confidence=round(float(d.get("confidence", 1.0)), 4),
                evidence_ids=list(d.get("evidence_ids", [])),
            )
            for u, v, k, d in self._g.edges(keys=True, data=True)
        ]
        return CandidateGraph(
            graph_id=self.graph_id,
            candidate_id=self.candidate_id,
            job_id=self.job_id,
            nodes=nodes,
            edges=edges,
            evidence_ledger=list(ledger_entries or []),
            metadata={
                **self.metadata,
                "node_count": len(nodes),
                "edge_count": len(edges),
                "backend": "networkx",
            },
        )

    @classmethod
    def from_candidate_graph(cls, graph: CandidateGraph) -> "NetworkXGraphStore":
        """Import a frozen ``CandidateGraph`` back into a mutable store."""
        store = cls(graph.graph_id, graph.candidate_id, graph.job_id)
        store.metadata = dict(graph.metadata)
        for n in graph.nodes:
            store.add_node(
                n.id, n.type, n.label,
                confidence=n.confidence, evidence_ids=n.evidence_ids, attributes=n.attributes,
            )
        for e in graph.edges:
            store.add_edge(
                e.source_id, e.target_id, e.type,
                confidence=e.confidence, evidence_ids=e.evidence_ids,
            )
        return store

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable snapshot (export). Round-trips via :meth:`from_dict`."""
        return self.to_candidate_graph().model_dump(mode="json")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NetworkXGraphStore":
        return cls.from_candidate_graph(CandidateGraph.model_validate(payload))


def _union(*lists: Iterable[str]) -> list[str]:
    """Order-preserving union of string iterables."""
    seen: dict[str, None] = {}
    for lst in lists:
        for item in lst:
            seen.setdefault(item)
    return list(seen)
