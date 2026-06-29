"""Canonical DELULU v2 domain models — the single source of truth.

    from app.shared.models import Evidence, CandidateGraph, RoleDNA, HiringDecision

There is exactly one definition of each of these in the repository. Do not
redefine them anywhere else.
"""

from __future__ import annotations

from app.shared.models.evidence import Evidence, EvidenceLedgerEntry
from app.shared.models.graph import CandidateGraph, GraphEdge, GraphNode
from app.shared.models.ranking import CandidateRanking, RankedList
from app.shared.models.reasoning import (
    CandidateGap,
    CandidateReasoning,
    HiringDecision,
    InterviewFocus,
    Recommendation,
    ReasoningClaim,
)
from app.shared.models.role import RoleDNA

__all__ = [
    # evidence
    "Evidence",
    "EvidenceLedgerEntry",
    # graph
    "GraphNode",
    "GraphEdge",
    "CandidateGraph",
    # role
    "RoleDNA",
    # reasoning + decision
    "ReasoningClaim",
    "CandidateGap",
    "CandidateReasoning",
    "InterviewFocus",
    "Recommendation",
    "HiringDecision",
    # ranking
    "CandidateRanking",
    "RankedList",
]
