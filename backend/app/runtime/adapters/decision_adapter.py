"""DecisionEngineAdapter — Developer 4 sync DecisionEngine -> v2 DecisionEngine.

The native engine consumes a ``ReasoningResult``; the frozen
:class:`app.shared.interfaces.DecisionEngine` supplies a
:class:`app.shared.models.CandidateReasoning` (+ RoleDNA). This adapter reconstructs
the minimal ``ReasoningResult`` the native engine needs — using the severity-bucket
counts stamped by :class:`ReasoningEngineAdapter` when present (degrading safely when
absent) — invokes the untouched engine, and maps the native ``DecisionResult`` onto
the canonical :class:`HiringDecision`. Developer 4's engine is untouched.
"""

from __future__ import annotations

from app.intelligence.decision.decision_engine import DecisionEngine as NativeDecisionEngine
from app.intelligence.decision.decision_engine import (
    DecisionResult,
    Recommendation as NativeRecommendation,
)
from app.intelligence.reasoning.confidence_engine import ConfidenceResult
from app.intelligence.reasoning.gap_analyzer import GapAnalysis, GapItem
from app.intelligence.reasoning.reasoning_engine import ReasoningResult
from app.intelligence.reasoning.summary_composer import ReasoningSummary
from app.intelligence.reasoning.uncertainty_detector import UncertaintyAnalysis, UncertaintyItem
from app.shared.enums import GapSeverity, RecommendationAction, RecommendationLevel
from app.shared.models import (
    CandidateReasoning,
    HiringDecision,
    InterviewFocus,
    Recommendation,
    RoleDNA,
)

# Native recommendation labels -> shared RecommendationLevel.
_RECOMMENDATION_MAP = {
    NativeRecommendation.STRONG_HIRE: RecommendationLevel.STRONG_HIRE,
    NativeRecommendation.HIRE: RecommendationLevel.HIRE,
    NativeRecommendation.INTERVIEW: RecommendationLevel.LEAN_HIRE,
    NativeRecommendation.INTERVIEW_WITH_REVIEW: RecommendationLevel.LEAN_HIRE,
    NativeRecommendation.NEEDS_MORE_INFORMATION: RecommendationLevel.INSUFFICIENT_EVIDENCE,
    NativeRecommendation.REJECT: RecommendationLevel.NO_HIRE,
}

# Recommendation level -> suggested recruiter action.
_ACTION_MAP = {
    RecommendationLevel.STRONG_HIRE: RecommendationAction.FAST_TRACK,
    RecommendationLevel.HIRE: RecommendationAction.INTERVIEW,
    RecommendationLevel.LEAN_HIRE: RecommendationAction.INTERVIEW,
    RecommendationLevel.INSUFFICIENT_EVIDENCE: RecommendationAction.HOLD,
    RecommendationLevel.NO_HIRE: RecommendationAction.REJECT,
}

# Shared GapSeverity -> native gap bucket name.
_SEVERITY_BUCKET = {
    GapSeverity.BLOCKING: "critical",
    GapSeverity.MODERATE: "moderate",
    GapSeverity.MINOR: "minor",
}


def _unc_item(text: str, severity: str) -> UncertaintyItem:
    return UncertaintyItem(
        category="reconstructed", title=text[:60], severity=severity, rationale=text
    )


def _rebuild_reasoning_result(reasoning: CandidateReasoning) -> ReasoningResult:
    """Reconstruct the native ReasoningResult the DecisionEngine consumes.

    Gap severities round-trip exactly (CandidateGap carries severity). Uncertainty
    bucketing uses the counts stamped by ReasoningEngineAdapter; absent those, all
    uncertainty strings go to the ``low`` bucket — a safe default that never invents
    high-severity blockers.
    """
    meta = reasoning.metadata or {}

    gaps = GapAnalysis()
    for gap in reasoning.gaps:
        bucket = _SEVERITY_BUCKET.get(gap.severity, "moderate")
        getattr(gaps, bucket).append(
            GapItem(
                category="",
                title=gap.requirement,
                severity=bucket,
                rationale=gap.note,
                missing_evidence=[],
            )
        )

    unc = UncertaintyAnalysis()
    strings = list(reasoning.uncertainties)
    high = int(meta.get("uncertainties_high", 0))
    medium = int(meta.get("uncertainties_medium", 0))
    idx = 0
    for _ in range(min(high, len(strings))):
        unc.high.append(_unc_item(strings[idx], "high"))
        idx += 1
    for _ in range(min(medium, max(0, len(strings) - idx))):
        unc.medium.append(_unc_item(strings[idx], "medium"))
        idx += 1
    for text in strings[idx:]:
        unc.low.append(_unc_item(text, "low"))

    confidence = ConfidenceResult(
        overall_confidence=reasoning.overall_confidence,
        claim_confidence=reasoning.overall_confidence,
        evidence_confidence=reasoning.overall_confidence,
        uncertainty_penalty=0.0,
        explanation=str(meta.get("confidence_explanation", "")),
    )
    summary = ReasoningSummary(
        strengths=list(meta.get("strengths", [])),
        gaps=[],
        uncertainties=[],
        confidence_text="",
        overall_summary=reasoning.summary,
    )
    return ReasoningResult(
        claims=list(reasoning.claims),
        gaps=gaps,
        uncertainties=unc,
        confidence=confidence,
        summary=summary,
    )


def _to_hiring_decision(
    reasoning: CandidateReasoning, decision: DecisionResult
) -> HiringDecision:
    level = _RECOMMENDATION_MAP.get(
        decision.recommendation, RecommendationLevel.INSUFFICIENT_EVIDENCE
    )
    interview_focus = [
        InterviewFocus(
            topic=gap.requirement,
            rationale=gap.note or f"Probe {gap.requirement}.",
        )
        for gap in reasoning.gaps
        if gap.severity in (GapSeverity.BLOCKING, GapSeverity.MODERATE)
    ][:5]
    recommendations = [
        Recommendation(
            action=_ACTION_MAP.get(level, RecommendationAction.HOLD),
            rationale=decision.next_step,
            priority=1,
        )
    ]
    return HiringDecision(
        decision_id=f"decision:{reasoning.candidate_id}:{reasoning.job_id}",
        candidate_id=reasoning.candidate_id,
        job_id=reasoning.job_id,
        recommendation=level,
        confidence=max(0.0, min(1.0, reasoning.overall_confidence)),
        derived_score=max(0.0, min(1.0, decision.score)),
        reasons=list(decision.rationale),
        reservations=list(decision.blockers),
        interview_focus=interview_focus,
        missing_evidence=[gap.requirement for gap in reasoning.gaps],
        recommendations=recommendations,
        summary=reasoning.summary or "; ".join(decision.rationale),
        metadata={
            "native_recommendation": decision.recommendation.value,
            "next_step": decision.next_step,
        },
    )


class DecisionEngineAdapter:
    """Adapt Developer 4's DecisionEngine to the v2 ``DecisionEngine`` Protocol."""

    def __init__(self, engine: NativeDecisionEngine | None = None) -> None:
        self._engine = engine or NativeDecisionEngine()

    async def decide(self, reasoning: CandidateReasoning, role: RoleDNA) -> HiringDecision:
        native_result = _rebuild_reasoning_result(reasoning)
        decision: DecisionResult = self._engine.decide(native_result)
        return _to_hiring_decision(reasoning, decision)
