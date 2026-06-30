"""Confidence Fusion Engine — combine multi-source evidence into one score.

Each canonical entity accumulates evidence from several sources at different
intrinsic confidences. The fusion engine collapses them into a single, calibrated
node/edge confidence using **weighted probability-of-support**:

    final = 1 - Π_i (1 - w_i · c_i)

where ``w_i`` is the source trust weight (``SOURCE_WEIGHTS``) and ``c_i`` is the
source-intrinsic confidence of evidence ``i``. The form is monotonic: more
corroboration never lowers the score, and a single high-trust proof (GitHub,
certification) dominates a weak self-claim (resume).

Worked example
--------------
    resume   says Python @ 0.60  (w=0.60)
    github   proves Python @ 0.90 (w=1.00)
    linkedin says Python @ 0.70  (w=0.75)
    -> 1 - (1-0.36)(1-0.90)(1-0.525) = 0.9696  (high — three independent sources)

Beyond the fused score the engine reports claim *strength* (how corroborated) and
per-source reliability, which feed explainability and verification-status
promotion (single-source -> CORROBORATED when ≥2 independent sources agree).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

# Canonical weights live in the shared foundation (single source of truth).
from app.shared.constants import DEFAULT_SOURCE_WEIGHT, SOURCE_WEIGHTS
from app.shared.enums import VerificationStatus

logger = logging.getLogger(__name__)


def source_weight(source: str) -> float:
    """Trust weight for a source key (``EvidenceSource.value``)."""
    return SOURCE_WEIGHTS.get(source.lower(), DEFAULT_SOURCE_WEIGHT)


def fuse_confidence(evidence: list[tuple[str, float]]) -> float:
    """Probability-of-support fusion: ``final = 1 - Π(1 - weight * confidence)``.

    ``evidence`` is a list of ``(source, confidence)`` tuples. Kept as a free
    function for back-compat; :class:`ConfidenceFusionEngine` is the richer API.
    """
    if not evidence:
        return 0.0
    remaining = 1.0
    for source, confidence in evidence:
        support = max(0.0, min(1.0, source_weight(source) * confidence))
        remaining *= 1.0 - support
    return round(1.0 - remaining, 4)


@dataclass
class FusionResult:
    """The full outcome of fusing one entity's evidence."""

    confidence: float                         # fused [0,1]
    claim_strength: float                     # corroboration score [0,1]
    source_count: int                         # distinct sources
    top_source: str | None                    # highest-contribution source
    verification_status: VerificationStatus
    per_source: dict[str, float] = field(default_factory=dict)  # source -> max contribution


class ConfidenceFusionEngine:
    """Fuse weighted, multi-source evidence into a calibrated confidence."""

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        default_weight: float = DEFAULT_SOURCE_WEIGHT,
    ) -> None:
        self.weights = {k.lower(): v for k, v in (weights or SOURCE_WEIGHTS).items()}
        self.default_weight = default_weight

    def weight_of(self, source: str) -> float:
        return self.weights.get(source.lower(), self.default_weight)

    def fuse(self, evidence: list[tuple[str, float]]) -> float:
        """Just the fused score (thin wrapper over :func:`fuse_confidence`)."""
        if not evidence:
            return 0.0
        remaining = 1.0
        for source, confidence in evidence:
            support = max(0.0, min(1.0, self.weight_of(source) * confidence))
            remaining *= 1.0 - support
        return round(1.0 - remaining, 4)

    def fuse_detailed(self, evidence: list[tuple[str, float]]) -> FusionResult:
        """Fused score plus claim strength, source reliability, and status."""
        if not evidence:
            return FusionResult(0.0, 0.0, 0, None, VerificationStatus.UNVERIFIED)

        per_source: dict[str, float] = {}
        for source, conf in evidence:
            contribution = max(0.0, min(1.0, self.weight_of(source) * conf))
            key = source.lower()
            per_source[key] = max(per_source.get(key, 0.0), contribution)

        confidence = self.fuse(evidence)
        sources = sorted(per_source, key=lambda s: per_source[s], reverse=True)
        return FusionResult(
            confidence=confidence,
            claim_strength=self._claim_strength(per_source),
            source_count=len(per_source),
            top_source=sources[0] if sources else None,
            verification_status=self._status(per_source),
            per_source={s: round(v, 4) for s, v in per_source.items()},
        )

    # --- internals -----------------------------------------------------------

    def _claim_strength(self, per_source: dict[str, float]) -> float:
        """How well-corroborated a claim is: blends source breadth + strongest proof.

        One strong source -> moderate strength; several agreeing sources -> high.
        """
        if not per_source:
            return 0.0
        breadth = 1.0 - 1.0 / (1 + len(per_source))   # 1 src=0.5, 2=0.67, 3=0.75 ...
        strongest = max(per_source.values())
        return round(0.5 * breadth + 0.5 * strongest, 4)

    def _status(self, per_source: dict[str, float]) -> VerificationStatus:
        if "manual" in per_source:
            return VerificationStatus.VERIFIED
        if len(per_source) >= 2:
            return VerificationStatus.CORROBORATED
        return VerificationStatus.UNVERIFIED
