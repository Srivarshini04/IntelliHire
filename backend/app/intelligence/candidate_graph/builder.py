"""GraphBuilder — orchestrates raw Evidence into a unified CandidateGraph.

This is the centerpiece of the Graph Intelligence Layer. It runs the pipeline:

    Evidence  ->  Evidence Ledger      (immutable record of every claim)
              ->  Entity Resolution    (canonical nodes for skills/orgs/...)
              ->  Graph Construction    (candidate + entity nodes/edges, evidence-bound)
              ->  Duplicate Detection    (collapse near-duplicate nodes)
              ->  Relationship Inference (grow hidden edges/capabilities)
              ->  Confidence Fusion      (final per-node/edge calibrated scores)
              ->  CandidateGraph         (frozen shared model -> API/DB)

Ordering note: duplicate detection runs *before* fusion (not last) on purpose —
fusing first would leave merged nodes with stale confidence. All spec stages are
present; only their order is chosen for correctness.

The builder is pure/deterministic given its inputs and has no I/O: it accepts a
``list[Evidence]`` and returns a ``CandidateGraph``. Persistence and provider
extraction live in other layers.
"""

from __future__ import annotations

import logging

from app.intelligence.candidate_graph.confidence_fusion import ConfidenceFusionEngine
from app.intelligence.candidate_graph.dedup import DuplicateDetector
from app.intelligence.candidate_graph.entity_resolver import EntityResolver
from app.intelligence.candidate_graph.graph_store import NetworkXGraphStore
from app.intelligence.candidate_graph.inference import RelationshipInferenceEngine
from app.intelligence.candidate_graph.ledger import EvidenceLedger
from app.shared.enums import GraphNodeType
from app.shared.models.evidence import Evidence, EvidenceLedgerEntry
from app.shared.models.graph import CandidateGraph

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Assemble Evidence into a fused, inferred, de-duplicated CandidateGraph."""

    def __init__(
        self,
        resolver: EntityResolver | None = None,
        fusion: ConfidenceFusionEngine | None = None,
        inference: RelationshipInferenceEngine | None = None,
        dedup: DuplicateDetector | None = None,
        *,
        enable_inference: bool = True,
        enable_dedup: bool = True,
    ) -> None:
        self.resolver = resolver or EntityResolver()
        self.fusion = fusion or ConfidenceFusionEngine()
        self.inference = inference or RelationshipInferenceEngine(self.resolver)
        self.dedup = dedup or DuplicateDetector(self.resolver)
        self.enable_inference = enable_inference
        self.enable_dedup = enable_dedup

    def build(
        self,
        candidate_id: str,
        evidence: list[Evidence],
        job_id: str | None = None,
    ) -> CandidateGraph:
        """Build the unified graph for one candidate from their evidence."""
        graph_id = f"graph:{candidate_id}" + (f":{job_id}" if job_id else "")
        logger.info(
            "GraphBuilder.build candidate=%s job=%s evidence=%d",
            candidate_id, job_id, len(evidence),
        )

        # 1. Evidence Ledger — immutable system of record.
        ledger = EvidenceLedger()
        ledger.add_all(evidence)

        # 2-3. Entity resolution + graph construction.
        store = NetworkXGraphStore(graph_id, candidate_id, job_id)
        candidate_node_id = f"candidate:{candidate_id}"
        store.add_node(candidate_node_id, GraphNodeType.CANDIDATE, candidate_id, confidence=1.0)

        ledger_entries: dict[str, EvidenceLedgerEntry] = {}
        for ev in ledger.all():
            resolved = self.resolver.resolve(ev.entity_ref, ev.evidence_type)
            store.add_node(
                resolved.node_id, resolved.node_type, resolved.label,
                confidence=ev.confidence, evidence_ids=[ev.evidence_id],
                attributes={**ev.provenance, "resolution": resolved.method},
            )
            store.add_edge(
                candidate_node_id, resolved.node_id, resolved.candidate_edge,
                confidence=ev.confidence, evidence_ids=[ev.evidence_id],
            )
            ledger_entries[ev.evidence_id] = EvidenceLedgerEntry.from_evidence(
                ev, supporting_node_id=resolved.node_id
            )

        # 4. Duplicate Detection — collapse near-duplicate nodes (before fusion).
        if self.enable_dedup:
            for pair in self.dedup.collapse(store):
                self._remap_ledger(ledger_entries, drop=pair.drop_id, keep=pair.keep_id)

        # 5. Relationship Inference — grow hidden edges / inferred capabilities.
        if self.enable_inference:
            self.inference.expand(store, candidate_node_id)

        # 6. Confidence Fusion — final, calibrated per-node/edge scores.
        self._fuse(store, ledger, ledger_entries)

        graph = store.to_candidate_graph(ledger_entries.values())
        graph.metadata.update(
            {
                "evidence_count": len(ledger),
                "candidate_node_id": candidate_node_id,
                "inference_enabled": self.enable_inference,
                "dedup_enabled": self.enable_dedup,
            }
        )
        logger.info(
            "GraphBuilder.build done nodes=%d edges=%d",
            len(graph.nodes), len(graph.edges),
        )
        return graph

    # --- internals -----------------------------------------------------------

    def _fuse(
        self,
        store: NetworkXGraphStore,
        ledger: EvidenceLedger,
        ledger_entries: dict[str, EvidenceLedgerEntry],
    ) -> None:
        """Set each node's fused confidence + claim strength from the ledger."""
        for node_id in store.node_ids():
            data = store.get_node(node_id) or {}
            ev_ids = data.get("evidence_ids", [])
            pairs = [
                (ev.source.value, ev.confidence)
                for eid in ev_ids
                if (ev := ledger.get(eid)) is not None
            ]
            if not pairs:
                continue  # pure-inferred node — keep its discounted confidence
            result = self.fusion.fuse_detailed(pairs)
            store.set_node_confidence(node_id, result.confidence)
            store.update_node_attributes(
                node_id,
                claim_strength=result.claim_strength,
                source_count=result.source_count,
                top_source=result.top_source,
                verification_status=result.verification_status.value,
                fused_sources=result.per_source,
            )
            # Promote bound ledger entries' verification status to match corroboration.
            for eid in ev_ids:
                entry = ledger_entries.get(eid)
                if entry is not None:
                    entry.verification_status = result.verification_status

        # Fuse observed (non-inferred) edges from their own evidence.
        for u, v, _key, edata in store.edges():
            if edata.get("attributes", {}).get("inferred"):
                continue
            pairs = [
                (ev.source.value, ev.confidence)
                for eid in edata.get("evidence_ids", [])
                if (ev := ledger.get(eid)) is not None
            ]
            if pairs:
                store.set_edge_confidence(u, v, edata["type"], self.fusion.fuse(pairs))

    @staticmethod
    def _remap_ledger(
        ledger_entries: dict[str, EvidenceLedgerEntry], *, drop: str, keep: str
    ) -> None:
        """After a node merge, repoint bound ledger entries to the surviving node."""
        for entry in ledger_entries.values():
            if entry.supporting_node_id == drop:
                entry.supporting_node_id = keep
