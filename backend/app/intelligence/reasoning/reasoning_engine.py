"""Orchestrate the DELULU v2 reasoning pipeline (coordination only, no algorithms)."""

from __future__ import annotations

from dataclasses import dataclass

from app.intelligence.reasoning.claim_synthesizer import ClaimSynthesizer
from app.intelligence.reasoning.types import MaterialityMap
from app.intelligence.reasoning.confidence_engine import ConfidenceEngine, ConfidenceResult
from app.intelligence.reasoning.gap_analyzer import GapAnalysis, GapAnalyzer
from app.intelligence.reasoning.summary_composer import ReasoningSummary, SummaryComposer
from app.intelligence.reasoning.uncertainty_detector import UncertaintyAnalysis, UncertaintyDetector
from app.shared.models import CandidateGraph, ReasoningClaim, RoleDNA


@dataclass(frozen=True)
class ReasoningResult:
    """Structured output from one reasoning pipeline execution."""

    claims: list[ReasoningClaim]
    gaps: GapAnalysis
    uncertainties: UncertaintyAnalysis
    confidence: ConfidenceResult
    summary: ReasoningSummary


def _validate_inputs(graph: CandidateGraph, role: RoleDNA) -> None:
    if not isinstance(graph, CandidateGraph):
        raise TypeError("graph must be a CandidateGraph instance")
    if not isinstance(role, RoleDNA):
        raise TypeError("role must be a RoleDNA instance")
    if not graph.candidate_id or not str(graph.candidate_id).strip():
        raise ValueError("CandidateGraph.candidate_id is required")
    if not role.job_id or not str(role.job_id).strip():
        raise ValueError("RoleDNA.job_id is required")


class ReasoningEngine:
    """Coordinate claim synthesis, gap/uncertainty analysis, confidence, and summary."""

    def __init__(
        self,
        *,
        claim_synthesizer: ClaimSynthesizer | None = None,
        gap_analyzer: GapAnalyzer | None = None,
        uncertainty_detector: UncertaintyDetector | None = None,
        confidence_engine: ConfidenceEngine | None = None,
        summary_composer: SummaryComposer | None = None,
        materiality_map: MaterialityMap | None = None,
    ) -> None:
        self._claim_synthesizer = claim_synthesizer or ClaimSynthesizer()
        self._gap_analyzer = gap_analyzer or GapAnalyzer()
        self._uncertainty_detector = uncertainty_detector or UncertaintyDetector()
        self._confidence_engine = confidence_engine or ConfidenceEngine()
        self._summary_composer = summary_composer or SummaryComposer()
        self._materiality_map = materiality_map or MaterialityMap()

    def reason(self, graph: CandidateGraph, role: RoleDNA) -> ReasoningResult:
        """Run the reasoning pipeline for one (candidate, job) pair."""
        _validate_inputs(graph, role)

        claims = self._claim_synthesizer.synthesize(graph, self._materiality_map, role)
        gaps = self._gap_analyzer.analyze(graph, role, claims)
        uncertainties = self._uncertainty_detector.detect(graph, role, claims, gaps)
        confidence = self._confidence_engine.compute(claims, gaps, uncertainties)
        summary = self._summary_composer.compose(claims, gaps, uncertainties, confidence)

        return ReasoningResult(
            claims=claims,
            gaps=gaps,
            uncertainties=uncertainties,
            confidence=confidence,
            summary=summary,
        )
