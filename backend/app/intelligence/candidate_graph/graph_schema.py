"""DEPRECATED SHIM — canonical definitions now live in ``app.shared.models``.

This module previously defined the candidate-graph schemas. They have moved to the
shared foundation so there is exactly one definition each. Imports here still work
via re-export + back-compat aliases. Prefer importing from ``app.shared.models``.

Field rename in the canonical models: ``entities`` -> ``nodes``,
``relationships`` -> ``edges``.
"""

from __future__ import annotations

from app.shared.models.evidence import EvidenceLedgerEntry
from app.shared.models.graph import CandidateGraph, GraphEdge, GraphNode

# Back-compat aliases (pre-v2 names) — do not use in new code.
GraphEntity = GraphNode
GraphRelationship = GraphEdge
UnifiedCandidateGraph = CandidateGraph

__all__ = [
    "EvidenceLedgerEntry",
    "GraphNode",
    "GraphEdge",
    "CandidateGraph",
    "GraphEntity",
    "GraphRelationship",
    "UnifiedCandidateGraph",
]
