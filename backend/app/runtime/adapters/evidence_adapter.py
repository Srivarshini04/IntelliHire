"""EvidenceProviderAdapter — Developer 2 evidence sources -> v2 EvidenceProvider.

Developer 2's stack returns rich, source-specific ``dict`` packages and standardizes
them into :class:`app.services.evidence.base.EvidenceObject` via
:func:`app.services.evidence.normalizer.normalize`. The frozen v2 contract
(:class:`app.shared.interfaces.EvidenceProvider`) instead emits canonical, atomic
:class:`app.shared.models.Evidence`.

This adapter is the single ``EvidenceObject -> Evidence`` conversion point. It does
NOT fetch sources, score for a role, or assert absence (DECISION C): a failed/empty
source yields an empty list, never an "absent" Evidence object. Developer 2's code is
not modified.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable

from app.services.evidence.base import EvidenceObject
from app.services.evidence.normalizer import normalize as default_normalize
from app.shared.enums import (
    EvidencePolarity,
    EvidenceSource,
    EvidenceType,
    VerificationStatus,
)
from app.shared.models import Evidence

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
    """Minimal id formation (lowercase + underscores). NOT entity resolution."""
    return _SLUG_RE.sub("_", value.strip().lower()).strip("_") or "unknown"


def _confidence(obj: EvidenceObject) -> float:
    """Source-intrinsic confidence in [0,1] (relevance is 0..100; reliability is 0..1)."""
    if obj.relevance_score is not None:
        return max(0.0, min(1.0, obj.relevance_score / 100.0))
    return max(0.0, min(1.0, obj.reliability))


class EvidenceProviderAdapter:
    """Adapt one legacy evidence source to the v2 ``EvidenceProvider`` Protocol.

    Construct one per :class:`EvidenceSource`. ``collect`` receives the already-fetched
    raw source payload, normalizes it through Developer 2's ``normalize`` and converts
    the resulting :class:`EvidenceObject` into atomic :class:`Evidence`.
    """

    def __init__(
        self,
        source: EvidenceSource,
        *,
        normalizer: Callable[[str, dict[str, Any]], EvidenceObject] = default_normalize,
    ) -> None:
        self.source = source
        self._normalize = normalizer

    async def collect(self, candidate_id: str, raw: dict[str, Any]) -> list[Evidence]:
        obj = self._normalize(self.source.value, raw or {})
        if not obj.ok:
            # DECISION C: never emit absence/failure as Evidence; degrade gracefully.
            logger.info(
                "evidence source '%s' unusable for %s: %s",
                self.source.value,
                candidate_id,
                obj.error,
            )
            return []
        return self._to_evidence(candidate_id, obj)

    def _to_evidence(self, candidate_id: str, obj: EvidenceObject) -> list[Evidence]:
        base_conf = _confidence(obj)
        out: list[Evidence] = []

        # One SKILL observation per detected skill.
        for skill in obj.skills:
            out.append(
                Evidence(
                    evidence_id=f"ev:{self.source.value}:{candidate_id}:skill:{_slug(skill)}",
                    candidate_id=candidate_id,
                    source=self.source,
                    evidence_type=EvidenceType.SKILL,
                    entity_ref=f"skill:{_slug(skill)}",
                    claim=f"{skill} observed in {self.source.value}.",
                    polarity=EvidencePolarity.SUPPORTS,
                    confidence=base_conf,
                    provenance={"summary": obj.summary, "reliability": obj.reliability},
                    verification_status=VerificationStatus.UNVERIFIED,
                )
            )

        # One ASSESSMENT observation carrying the source-level summary + signals.
        if obj.summary or obj.signals:
            out.append(
                Evidence(
                    evidence_id=f"ev:{self.source.value}:{candidate_id}:summary",
                    candidate_id=candidate_id,
                    source=self.source,
                    evidence_type=EvidenceType.ASSESSMENT,
                    entity_ref=f"{self.source.value}:{candidate_id}",
                    claim=obj.summary or f"{self.source.value} evidence collected.",
                    polarity=EvidencePolarity.SUPPORTS,
                    confidence=base_conf,
                    provenance={
                        "signals": [s.model_dump() for s in obj.signals],
                        "highlights": obj.highlights,
                        "source_url": obj.source_url,
                        "processed": obj.processed,
                    },
                    verification_status=VerificationStatus.UNVERIFIED,
                )
            )

        return out
