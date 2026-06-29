"""Compute deterministic overall reasoning confidence from claims, gaps, and uncertainties.

Pure read-only scoring — no ranking, hiring recommendations, summaries, or mutation.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.intelligence.reasoning.gap_analyzer import GapAnalysis
from app.intelligence.reasoning.uncertainty_detector import UncertaintyAnalysis
from app.shared.enums import Intensity
from app.shared.models import ReasoningClaim

_STRONG_CLAIM_THRESHOLD = 0.75
_CRITICAL_GAP_PENALTY = 0.12
_MODERATE_GAP_PENALTY = 0.06
_MINOR_GAP_PENALTY = 0.03
_HIGH_UNCERTAINTY_PENALTY = 0.10
_MEDIUM_UNCERTAINTY_PENALTY = 0.05
_LOW_UNCERTAINTY_PENALTY = 0.02
_FEW_CLAIMS_PENALTY = 0.08
_NO_CLAIMS_PENALTY = 0.30
_STRONG_CLAIM_BONUS = 0.03
_MAX_STRONG_CLAIM_BONUS = 0.12
_MATERIALITY_WEIGHT = {
    Intensity.CRITICAL: 1.0,
    Intensity.HIGH: 0.9,
    Intensity.MEDIUM: 0.7,
    Intensity.LOW: 0.5,
    Intensity.NONE: 0.3,
}


@dataclass(frozen=True)
class ConfidenceResult:
    """Deterministic confidence projection for one reasoning pass."""

    overall_confidence: float
    claim_confidence: float
    evidence_confidence: float
    uncertainty_penalty: float
    explanation: str


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def _supported_claims(claims: list[ReasoningClaim]) -> list[ReasoningClaim]:
    return [claim for claim in claims if claim.supporting_evidence_ids]


def _strong_claims(claims: list[ReasoningClaim]) -> list[ReasoningClaim]:
    return [
        claim
        for claim in _supported_claims(claims)
        if claim.confidence >= _STRONG_CLAIM_THRESHOLD
        and not claim.counter_evidence_ids
    ]


def _compute_claim_confidence(claims: list[ReasoningClaim]) -> float:
    """Weighted mean of per-claim confidence using role materiality."""
    supported = _supported_claims(claims)
    if not supported:
        return 0.0

    total_weight = 0.0
    weighted_sum = 0.0
    for claim in supported:
        weight = _MATERIALITY_WEIGHT.get(claim.materiality, 0.7)
        total_weight += weight
        weighted_sum += claim.confidence * weight

    return _clamp_score(weighted_sum / total_weight)


def _compute_evidence_confidence(claims: list[ReasoningClaim]) -> float:
    """Corroboration strength from supporting vs counter evidence on claims."""
    supported = _supported_claims(claims)
    if not supported:
        return 0.0

    scores: list[float] = []
    for claim in supported:
        support_count = len(claim.supporting_evidence_ids)
        counter_count = len(claim.counter_evidence_ids)
        corroboration = support_count / (support_count + counter_count + 1)
        diversity_bonus = min(0.15, max(0, support_count - 1) * 0.05)
        scores.append(_clamp_score(claim.confidence * corroboration + diversity_bonus))

    return _clamp_score(sum(scores) / len(scores))


def _compute_gap_penalty(gaps: GapAnalysis) -> float:
    penalty = (
        len(gaps.critical) * _CRITICAL_GAP_PENALTY
        + len(gaps.moderate) * _MODERATE_GAP_PENALTY
        + len(gaps.minor) * _MINOR_GAP_PENALTY
    )
    return round(min(0.6, penalty), 4)


def _compute_uncertainty_item_penalty(uncertainties: UncertaintyAnalysis) -> float:
    penalty = (
        len(uncertainties.high) * _HIGH_UNCERTAINTY_PENALTY
        + len(uncertainties.medium) * _MEDIUM_UNCERTAINTY_PENALTY
        + len(uncertainties.low) * _LOW_UNCERTAINTY_PENALTY
    )
    return round(min(0.5, penalty), 4)


def _compute_claim_adjustment(claims: list[ReasoningClaim]) -> float:
    """Bonus for many strong claims; penalty when claims are sparse."""
    if not claims:
        return -_NO_CLAIMS_PENALTY

    adjustment = 0.0
    if len(claims) < 2:
        adjustment -= _FEW_CLAIMS_PENALTY

    strong_bonus = min(_MAX_STRONG_CLAIM_BONUS, len(_strong_claims(claims)) * _STRONG_CLAIM_BONUS)
    adjustment += strong_bonus
    return round(adjustment, 4)


def _build_explanation(
    overall: float,
    claims: list[ReasoningClaim],
    gaps: GapAnalysis,
    uncertainties: UncertaintyAnalysis,
    gap_penalty: float,
    uncertainty_item_penalty: float,
) -> str:
    """Short deterministic summary of how the score was derived."""
    strong_count = len(_strong_claims(claims))
    return (
        f"Overall confidence {overall:.2f} from {len(claims)} claim(s) "
        f"({strong_count} strong), "
        f"{gaps.total_count()} gap(s) (-{gap_penalty:.2f}), "
        f"{uncertainties.total_count()} uncertainty signal(s) (-{uncertainty_item_penalty:.2f})."
    )


class ConfidenceEngine:
    """Compute how reliable the current reasoning output is."""

    def compute(
        self,
        claims: list[ReasoningClaim],
        gaps: GapAnalysis,
        uncertainties: UncertaintyAnalysis,
    ) -> ConfidenceResult:
        """Return a deterministic confidence projection without mutating inputs."""
        claim_confidence = _compute_claim_confidence(claims)
        evidence_confidence = _compute_evidence_confidence(claims)
        gap_penalty = _compute_gap_penalty(gaps)
        uncertainty_item_penalty = _compute_uncertainty_item_penalty(uncertainties)
        uncertainty_penalty = round(gap_penalty + uncertainty_item_penalty, 4)

        claim_nudge = (claim_confidence - 0.5) * 0.10 if claims else 0.0
        evidence_nudge = (evidence_confidence - 0.5) * 0.05 if claims else 0.0

        raw_overall = (
            1.0
            - gap_penalty
            - uncertainty_item_penalty
            + _compute_claim_adjustment(claims)
            + claim_nudge
            + evidence_nudge
        )
        overall_confidence = _clamp_score(raw_overall)

        explanation = _build_explanation(
            overall_confidence,
            claims,
            gaps,
            uncertainties,
            gap_penalty,
            uncertainty_item_penalty,
        )

        return ConfidenceResult(
            overall_confidence=overall_confidence,
            claim_confidence=claim_confidence,
            evidence_confidence=evidence_confidence,
            uncertainty_penalty=uncertainty_penalty,
            explanation=explanation,
        )
