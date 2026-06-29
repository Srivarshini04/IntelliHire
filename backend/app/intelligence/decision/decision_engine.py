"""Convert structured reasoning outputs into deterministic hiring recommendations.

Thin rule engine only — consumes ReasoningResult, performs no reasoning or graph access.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.intelligence.reasoning.confidence_engine import ConfidenceResult
from app.intelligence.reasoning.gap_analyzer import GapAnalysis, GapItem
from app.intelligence.reasoning.reasoning_engine import ReasoningResult
from app.intelligence.reasoning.summary_composer import ReasoningSummary
from app.intelligence.reasoning.uncertainty_detector import UncertaintyAnalysis, UncertaintyItem
from app.shared.models import ReasoningClaim


class Recommendation(str, Enum):
    """Deterministic hiring recommendation labels for the reasoning module."""

    STRONG_HIRE = "strong_hire"
    HIRE = "hire"
    INTERVIEW = "interview"
    INTERVIEW_WITH_REVIEW = "interview_with_review"
    NEEDS_MORE_INFORMATION = "needs_more_information"
    REJECT = "reject"


_MAX_RATIONALE = 5
_MAX_BLOCKERS = 5
_MULTIPLE_CRITICAL_GAPS = 2
_MULTIPLE_MODERATE_GAPS = 2

_NEXT_STEPS: dict[Recommendation, str] = {
    Recommendation.STRONG_HIRE: "Proceed to final interview.",
    Recommendation.HIRE: "Proceed to technical interview.",
    Recommendation.INTERVIEW: "Schedule technical interview.",
    Recommendation.INTERVIEW_WITH_REVIEW: "Recruiter review recommended.",
    Recommendation.NEEDS_MORE_INFORMATION: "Collect additional evidence.",
    Recommendation.REJECT: "Do not proceed.",
}


@dataclass(frozen=True)
class DecisionResult:
    """Deterministic hiring decision derived from reasoning outputs."""

    recommendation: Recommendation
    score: float
    rationale: list[str]
    blockers: list[str]
    next_step: str


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
    return out


def _supported_claim_count(claims: list[ReasoningClaim]) -> int:
    return sum(1 for claim in claims if claim.supporting_evidence_ids)


def _select_recommendation(
    confidence: float,
    gaps: GapAnalysis,
    uncertainties: UncertaintyAnalysis,
) -> Recommendation:
    critical_count = len(gaps.critical)
    moderate_count = len(gaps.moderate)
    high_uncertainty_count = len(uncertainties.high)

    if confidence < 0.35 or critical_count >= _MULTIPLE_CRITICAL_GAPS:
        return Recommendation.REJECT

    if moderate_count >= _MULTIPLE_MODERATE_GAPS or confidence < 0.50:
        return Recommendation.NEEDS_MORE_INFORMATION

    if confidence < 0.65:
        return Recommendation.INTERVIEW_WITH_REVIEW

    if confidence < 0.80:
        return Recommendation.INTERVIEW

    if critical_count > 0:
        return Recommendation.INTERVIEW

    if confidence < 0.90 or high_uncertainty_count > 0:
        return Recommendation.HIRE

    return Recommendation.STRONG_HIRE


def _collect_rationale(result: ReasoningResult) -> list[str]:
    lines: list[str] = []

    supported = _supported_claim_count(result.claims)
    if supported >= 2:
        lines.append("Multiple well-supported technical competencies.")
    elif supported == 1:
        lines.append("One well-supported competency identified.")
    elif not result.claims:
        lines.append("No synthesized reasoning claims available.")

    confidence = result.confidence.overall_confidence
    if confidence >= 0.90:
        lines.append("Overall confidence is very high.")
    elif confidence >= 0.75:
        lines.append("Overall confidence is high.")
    elif confidence >= 0.55:
        lines.append("Overall confidence is moderate.")
    else:
        lines.append("Overall confidence is low.")

    if not result.gaps.critical and not result.uncertainties.high:
        lines.append("No critical reasoning uncertainty.")
    elif result.uncertainties.high:
        lines.append("High-severity uncertainty signals remain.")

    for gap in result.gaps.moderate:
        text = gap.rationale.strip() or f"Moderate {gap.title} gap detected."
        if "moderate" not in text.lower():
            text = f"Moderate {gap.title} gap detected."
        lines.append(text)

    for item in result.summary.strengths[:2]:
        lines.append(item)

    return _dedupe_preserve_order(lines)[:_MAX_RATIONALE]


def _item_text(item: GapItem | UncertaintyItem) -> str:
    return item.rationale.strip() or item.title.strip()


def _collect_blockers(result: ReasoningResult) -> list[str]:
    blockers: list[str] = []
    for gap in result.gaps.critical:
        blockers.append(_item_text(gap))
    for uncertainty in result.uncertainties.high:
        blockers.append(_item_text(uncertainty))
    return _dedupe_preserve_order(blockers)[:_MAX_BLOCKERS]


def _next_step(recommendation: Recommendation) -> str:
    return _NEXT_STEPS[recommendation]


def _compute_score(result: ReasoningResult, recommendation: Recommendation) -> float:
    base = result.confidence.overall_confidence
    supported = _supported_claim_count(result.claims)
    bonus = min(0.05, max(0, supported - 1) * 0.01)
    penalty = len(result.gaps.critical) * 0.08 + len(result.uncertainties.high) * 0.06
    raw = base + bonus - penalty

    if recommendation == Recommendation.STRONG_HIRE:
        raw = max(raw, 0.90)
    elif recommendation == Recommendation.REJECT:
        raw = min(raw, 0.34)

    return _clamp_score(raw)


def _validate_input(result: ReasoningResult) -> None:
    if not isinstance(result, ReasoningResult):
        raise TypeError("result must be a ReasoningResult instance")


class DecisionEngine:
    """Map ReasoningResult to a deterministic hiring recommendation."""

    def decide(self, result: ReasoningResult) -> DecisionResult:
        """Produce a hiring decision without mutating the reasoning output."""
        _validate_input(result)

        recommendation = _select_recommendation(
            result.confidence.overall_confidence,
            result.gaps,
            result.uncertainties,
        )
        rationale = _collect_rationale(result)
        blockers = _collect_blockers(result)
        score = _compute_score(result, recommendation)
        next_step = _next_step(recommendation)

        return DecisionResult(
            recommendation=recommendation,
            score=score,
            rationale=rationale,
            blockers=blockers,
            next_step=next_step,
        )
