"""Candidate Graph Intelligence Layer.

Unifies evidence from every source into one connected knowledge graph that
validates claims, resolves entities, infers relationships, and fuses confidence.

Pipeline:  Evidence -> EvidenceLedger -> EntityResolver -> GraphBuilder
           -> RelationshipInferenceEngine -> ConfidenceFusionEngine
           -> DuplicateDetector -> CandidateGraph

Public surface::

    from app.intelligence.candidate_graph import GraphBuilder, EvidenceLedger
"""

from __future__ import annotations

from app.intelligence.candidate_graph.builder import GraphBuilder
from app.intelligence.candidate_graph.confidence_fusion import (
    ConfidenceFusionEngine,
    FusionResult,
    fuse_confidence,
)
from app.intelligence.candidate_graph.dedup import DuplicateDetector, DuplicatePair
from app.intelligence.candidate_graph.entity_resolver import (
    EntityResolver,
    ResolvedEntity,
    resolve_organization,
    resolve_skill,
)
from app.intelligence.candidate_graph.graph_store import (
    GraphStoreBackend,
    NetworkXGraphStore,
)
from app.intelligence.candidate_graph.inference import (
    InferredEdge,
    RelationshipInferenceEngine,
)
from app.intelligence.candidate_graph.ledger import EvidenceLedger
from app.intelligence.candidate_graph.registry import GraphRegistry, graph_registry
from app.intelligence.candidate_graph.report import GraphReport, build_report

__all__ = [
    "GraphBuilder",
    "EvidenceLedger",
    "EntityResolver",
    "ResolvedEntity",
    "resolve_skill",
    "resolve_organization",
    "NetworkXGraphStore",
    "GraphStoreBackend",
    "RelationshipInferenceEngine",
    "InferredEdge",
    "ConfidenceFusionEngine",
    "FusionResult",
    "fuse_confidence",
    "DuplicateDetector",
    "DuplicatePair",
    "GraphRegistry",
    "graph_registry",
    "GraphReport",
    "build_report",
]
