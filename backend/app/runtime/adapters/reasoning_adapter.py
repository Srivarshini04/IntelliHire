"""ReasoningEngineAdapter — Developer 4 sync ReasoningEngine -> v2 ReasoningEngine.

Developer 4's engine is synchronous and returns a native ``ReasoningResult``. The
frozen :class:`app.shared.interfaces.ReasoningEngine` is async and returns the
canonical :class:`app.shared.models.CandidateReasoning`. This adapter performs that
conversion and stamps the result's ``metadata`` with the severity-bucket counts and
strengths that :class:`DecisionEngineAdapter` needs to faithfully reconstruct the
native result downstream. Developer 4's engine is untouched.
"""

from __future__ import annotations

from app.intelligence.reasoning.gap_analyzer import GapAnalysis
from app.intelligence.reasoning.reasoning_engine import (
    ReasoningEngine as NativeReasoningEngine,
)
from app.intelligence.reasoning.reasoning_engine import ReasoningResult
from app.shared.enums import GapSeverity
from app.shared.models import CandidateGap, CandidateGraph, CandidateReasoning, RoleDNA

# Native gap-severity strings -> shared GapSeverity enum.
_GAP_SEVERITY = {
    "critical": GapSeverity.BLOCKING,
    "moderate": GapSeverity.MODERATE,
    "minor": GapSeverity.MINOR,
}


def _convert_gaps(gaps: GapAnalysis) -> list[CandidateGap]:
    return [
        CandidateGap(
            requirement=item.title,
            severity=_GAP_SEVERITY.get(item.severity, GapSeverity.MODERATE),
            note=item.rationale,
        )
        for item in gaps.all_items()
    ]


class ReasoningEngineAdapter:
    """Adapt Developer 4's ReasoningEngine to the v2 ``ReasoningEngine`` Protocol."""

    def __init__(self, engine: NativeReasoningEngine | None = None) -> None:
        self._engine = engine or NativeReasoningEngine()

    async def reason(self, graph: CandidateGraph, role: RoleDNA) -> CandidateReasoning:
        result: ReasoningResult = self._engine.reason(graph, role)
        return self._to_candidate_reasoning(graph.candidate_id, role.job_id, result)

    @staticmethod
    def _to_candidate_reasoning(
        candidate_id: str, job_id: str, result: ReasoningResult
    ) -> CandidateReasoning:
        uncertainties = [
            (item.rationale.strip() or item.title) for item in result.uncertainties.all_items()
        ]
        return CandidateReasoning(
            reasoning_id=f"reasoning:{candidate_id}:{job_id}",
            candidate_id=candidate_id,
            job_id=job_id,
            claims=list(result.claims),
            gaps=_convert_gaps(result.gaps),
            uncertainties=uncertainties,
            overall_confidence=result.confidence.overall_confidence,
            summary=result.summary.overall_summary,
            metadata={
                # Severity-bucket counts let DecisionEngineAdapter reconstruct the
                # native ReasoningResult faithfully (CandidateReasoning flattens them).
                "gaps_critical": len(result.gaps.critical),
                "gaps_moderate": len(result.gaps.moderate),
                "gaps_minor": len(result.gaps.minor),
                "uncertainties_high": len(result.uncertainties.high),
                "uncertainties_medium": len(result.uncertainties.medium),
                "uncertainties_low": len(result.uncertainties.low),
                "strengths": list(result.summary.strengths),
                "confidence_explanation": result.confidence.explanation,
            },
        )
