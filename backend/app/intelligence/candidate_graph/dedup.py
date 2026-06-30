"""Duplicate Detection System — collapse redundant nodes, keep all evidence.

Even after entity resolution, near-duplicate nodes survive: two providers spell a
project differently ("ClinicBot" vs "clinic-bot"), or a fuzzy miss leaves
"PostgreSQL" and "Postgres DB" as separate nodes. This engine finds such pairs
*within a node type* and merges them through ``GraphStore.merge_nodes``, which
unions evidence ids and rewires edges — so confidence and provenance survive the
merge (requirement: "preserve evidence links after merge").

Two signals decide a duplicate:
  1. identical canonical key (the resolver already agrees they're one entity), or
  2. fuzzy label similarity ≥ threshold for the de-dupable node types.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.intelligence.candidate_graph.entity_resolver import EntityResolver, _norm
from app.intelligence.candidate_graph.graph_store import NetworkXGraphStore
from app.shared.enums import GraphNodeType

logger = logging.getLogger(__name__)

# Node types where duplicates are worth collapsing.
DEDUPABLE_TYPES: tuple[GraphNodeType, ...] = (
    GraphNodeType.SKILL,
    GraphNodeType.TECHNOLOGY,
    GraphNodeType.PROJECT,
    GraphNodeType.REPOSITORY,
    GraphNodeType.ORGANIZATION,
)


@dataclass(frozen=True)
class DuplicatePair:
    keep_id: str
    drop_id: str
    node_type: GraphNodeType
    similarity: float
    reason: str  # 'canonical_key' | 'fuzzy_label'


class DuplicateDetector:
    """Detect and merge duplicate nodes within a :class:`NetworkXGraphStore`."""

    def __init__(self, resolver: EntityResolver | None = None, threshold: float = 0.9) -> None:
        self.resolver = resolver or EntityResolver()
        self.threshold = threshold

    def detect(self, store: NetworkXGraphStore) -> list[DuplicatePair]:
        """Find duplicate pairs without mutating the graph (idempotent, read-only)."""
        pairs: list[DuplicatePair] = []
        for node_type in DEDUPABLE_TYPES:
            pairs.extend(self._detect_within_type(store, node_type))
        return pairs

    def collapse(self, store: NetworkXGraphStore) -> list[DuplicatePair]:
        """Detect then merge. Returns the merges performed (for telemetry/audit)."""
        merged: list[DuplicatePair] = []
        gone: set[str] = set()
        for pair in self.detect(store):
            if pair.drop_id in gone or pair.keep_id in gone:
                continue  # a transitive merge already consumed one side
            store.merge_nodes(pair.keep_id, pair.drop_id)
            gone.add(pair.drop_id)
            merged.append(pair)
        if merged:
            logger.info("dedup collapsed %d duplicate node(s)", len(merged))
        return merged

    # --- internals -----------------------------------------------------------

    def _detect_within_type(
        self, store: NetworkXGraphStore, node_type: GraphNodeType
    ) -> list[DuplicatePair]:
        ids = store.nodes_of_type(node_type)
        pairs: list[DuplicatePair] = []
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                pair = self._compare(store, a, b, node_type)
                if pair:
                    pairs.append(pair)
        return pairs

    def _compare(
        self, store: NetworkXGraphStore, a: str, b: str, node_type: GraphNodeType
    ) -> DuplicatePair | None:
        na, nb = store.get_node(a), store.get_node(b)
        if not na or not nb:
            return None
        la, lb = na.get("label", a), nb.get("label", b)

        # 1. canonical-key agreement (resolver says same entity)
        if a == b or _norm(la) == _norm(lb):
            keep, drop = self._pick(store, a, b)
            return DuplicatePair(keep, drop, node_type, 1.0, "canonical_key")

        # 2. fuzzy label similarity
        sim = self.resolver.similarity(la, lb)
        if sim >= self.threshold:
            keep, drop = self._pick(store, a, b)
            return DuplicatePair(keep, drop, node_type, round(sim, 4), "fuzzy_label")
        return None

    def _pick(self, store: NetworkXGraphStore, a: str, b: str) -> tuple[str, str]:
        """Keep the node with more evidence (tie-break: shorter, more-canonical id)."""
        na, nb = store.get_node(a) or {}, store.get_node(b) or {}
        ea, eb = len(na.get("evidence_ids", [])), len(nb.get("evidence_ids", []))
        if ea != eb:
            return (a, b) if ea > eb else (b, a)
        return (a, b) if len(a) <= len(b) else (b, a)
