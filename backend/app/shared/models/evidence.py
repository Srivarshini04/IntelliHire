"""Evidence domain models — the atomic unit of the DELULU v2 'Evidence OS'.

Everything upstream of reasoning emits exactly one thing: Evidence.

DECISION B: Evidence carries source-intrinsic confidence + provenance only — never
role-specific importance. Materiality is computed later by the ReasoningEngine
against RoleDNA, so providers stay role-agnostic and reusable across every job.

DECISION C: Providers emit only *observed* facts. Absence ("no Kubernetes") is
never an Evidence object; missing requirements are derived in reasoning by diffing
the CandidateGraph against RoleDNA.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.fields import ConfidenceLevel, SourceSpan  # reuse existing primitives
from app.shared.enums import (
    EvidencePolarity,
    EvidenceSource,
    EvidenceType,
    VerificationStatus,
)


def _level(confidence: float) -> ConfidenceLevel:
    if confidence > 0.85:
        return ConfidenceLevel.GREEN
    if confidence >= 0.60:
        return ConfidenceLevel.YELLOW
    return ConfidenceLevel.RED


class Evidence(BaseModel):
    """An atomic, source-intrinsic claim emitted by an EvidenceProvider.

    One Evidence == one observation, from one source, about one canonical entity.
    """

    schema_version: Literal["1.0"] = "1.0"
    evidence_id: str = Field(..., description="Stable unique id, e.g. 'ev_github_0001'.")
    candidate_id: str
    source: EvidenceSource
    evidence_type: EvidenceType = Field(..., description="Category of the observed fact.")
    entity_ref: str = Field(
        ...,
        description="Canonical entity id from entity_resolver (e.g. 'skill:fastapi'). The fusion/dedup key.",
    )
    claim: str = Field(
        ...,
        description="Human-readable statement. Source text for the `reasoning` column + explainability.",
    )
    polarity: EvidencePolarity = Field(
        default=EvidencePolarity.SUPPORTS,
        description="SUPPORTS or CONTRADICTS. Contradictions are recorded, never subtracted in fusion.",
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Source-intrinsic likelihood the claim is true (0..1)."
    )
    provenance: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw supporting detail, e.g. {'repository': 'ClinicBot', 'commits': 214, 'files': 61}.",
    )
    source_span: SourceSpan | None = Field(
        default=None, description="Character-level pointer for UI source highlighting (resume/JD)."
    )
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED

    @property
    def confidence_level(self) -> ConfidenceLevel:
        return _level(self.confidence)


class EvidenceLedgerEntry(BaseModel):
    """Evidence after it has been placed into the CandidateGraph.

    Canonical ledger entry. The legacy
    ``app.intelligence.candidate_graph.graph_schema.EvidenceLedgerEntry`` now
    re-exports this type. Difference from raw Evidence: it is bound to a graph
    node via ``supporting_node_id``.
    """

    evidence_id: str
    candidate_id: str
    source: EvidenceSource
    evidence_type: EvidenceType
    entity_ref: str
    claim: str
    polarity: EvidencePolarity = EvidencePolarity.SUPPORTS
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    supporting_node_id: str = Field(..., description="GraphNode.id this evidence attaches to.")
    provenance: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED

    @property
    def confidence_level(self) -> ConfidenceLevel:
        return _level(self.confidence)

    @classmethod
    def from_evidence(cls, ev: Evidence, supporting_node_id: str) -> "EvidenceLedgerEntry":
        """Promote raw Evidence into a graph-bound ledger entry (used by GraphBuilder)."""
        return cls(
            evidence_id=ev.evidence_id,
            candidate_id=ev.candidate_id,
            source=ev.source,
            evidence_type=ev.evidence_type,
            entity_ref=ev.entity_ref,
            claim=ev.claim,
            polarity=ev.polarity,
            confidence=ev.confidence,
            supporting_node_id=supporting_node_id,
            provenance=ev.provenance,
            timestamp=ev.collected_at,
            verification_status=ev.verification_status,
        )
