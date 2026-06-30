"""Standardized Evidence objects + the common provider contract.

Every candidate-intelligence provider (GitHub, LinkedIn, LeetCode, Resume,
Portfolio) extracts data in its own shape. Downstream scoring engines, the
evidence store and the UI all benefit from one canonical representation, so
each provider also exposes its findings as an :class:`EvidenceObject`.

The object mirrors the persisted ``candidate_evidence`` row
(:class:`app.models.evidence.Evidence`) — ``source_type``, ``source_url``,
``raw_content``, ``processed_content``, ``relevance_score`` — and adds the
``reliability`` weight from :mod:`app.pipeline.evidence_sources` plus a small
set of human-readable fields (summary, skills, signals) that make evidence
explainable without re-parsing the raw payload.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.pipeline.evidence_sources import reliability


class EvidenceSignal(BaseModel):
    """A single explainable observation pulled from a source.

    Example: ``{"label": "hard_problems_solved", "detail": "42 hard problems",
    "weight": 0.85}``.
    """

    label: str
    detail: str = ""
    weight: float = 1.0
    value: Any | None = None


class EvidenceObject(BaseModel):
    """Canonical, source-agnostic evidence record.

    Providers return this so the pipeline can persist, score and explain
    evidence uniformly regardless of where it came from.
    """

    source: str
    source_url: str | None = None
    reliability: float = 0.4
    relevance_score: float | None = None
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    signals: list[EvidenceSignal] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
    processed: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def ok(self) -> bool:
        """True when the provider produced usable evidence."""
        return self.error is None

    def to_db_payload(self) -> dict[str, Any]:
        """Map onto the persisted ``Evidence`` ORM columns.

        ``processed_content`` keeps the explainable view (summary/skills/
        signals) so the candidate-detail API can render evidence without the
        bulky raw payload; ``raw_content`` keeps the original extraction.
        """
        return {
            "source_type": self.source,
            "source_url": self.source_url,
            "raw_content": self.raw or None,
            "processed_content": {
                "summary": self.summary,
                "skills": self.skills,
                "signals": [s.model_dump() for s in self.signals],
                "highlights": self.highlights,
                "reliability": self.reliability,
                **self.processed,
            },
            "relevance_score": self.relevance_score,
        }


def build_evidence(
    source: str,
    *,
    source_url: str | None = None,
    relevance_score: float | None = None,
    summary: str = "",
    skills: list[str] | None = None,
    signals: list[EvidenceSignal] | None = None,
    highlights: list[str] | None = None,
    raw: dict[str, Any] | None = None,
    processed: dict[str, Any] | None = None,
    error: str | None = None,
) -> EvidenceObject:
    """Construct an :class:`EvidenceObject`, auto-filling the reliability weight.

    Skills are de-duplicated while preserving order.
    """
    deduped: list[str] = []
    seen: set[str] = set()
    for skill in skills or []:
        key = str(skill).strip().lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(str(skill).strip())

    return EvidenceObject(
        source=source,
        source_url=source_url,
        reliability=reliability(source),
        relevance_score=relevance_score,
        summary=summary,
        skills=deduped,
        signals=signals or [],
        highlights=highlights or [],
        raw=raw or {},
        processed=processed or {},
        error=error,
    )


@runtime_checkable
class EvidenceProvider(Protocol):
    """Common contract every candidate-intelligence provider implements.

    Providers stay free to expose richer module-level functions (the existing
    ``analyze_*_evidence`` helpers); this protocol is the uniform entry point
    used by orchestration code that wants standardized evidence back.
    """

    source: str

    async def collect(
        self,
        identifier: str,
        role_blueprint: dict | None = None,
        **kwargs: Any,
    ) -> EvidenceObject:
        """Extract evidence for ``identifier`` (a URL or handle) and normalize it."""
        ...
