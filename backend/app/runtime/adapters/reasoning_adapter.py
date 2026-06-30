"""ReasoningEngineAdapter — Developer 4 sync ReasoningEngine -> v2 ReasoningEngine.

Developer 4's engine is synchronous and returns a native ``ReasoningResult``. The
frozen :class:`app.shared.interfaces.ReasoningEngine` is async and returns the
canonical :class:`app.shared.models.CandidateReasoning`. This adapter performs that
conversion and stamps the result's ``metadata`` with the severity-bucket counts and
strengths that :class:`DecisionEngineAdapter` needs to faithfully reconstruct the
native result downstream.

Graceful degradation (graph disabled): when the upstream graph carries
``metadata["graph_disabled"] == True`` (the NoOpGraphAdapter), there are no graph
nodes for Developer 4's ``ClaimSynthesizer`` to traverse. Rather than collapse every
candidate to "no hire", this adapter synthesizes claims **directly from the evidence**
the NoOpGraphAdapter passed through, then runs Developer 4's OWN gap / uncertainty /
confidence / summary engines over those claims. Only claim synthesis from evidence is
new; the rest is Developer 4's untouched logic.
"""

from __future__ import annotations

from app.intelligence.reasoning.confidence_engine import ConfidenceEngine
from app.intelligence.reasoning.gap_analyzer import GapAnalysis, GapAnalyzer
from app.intelligence.reasoning.reasoning_engine import (
    ReasoningEngine as NativeReasoningEngine,
)
from app.intelligence.reasoning.reasoning_engine import ReasoningResult
from app.intelligence.reasoning.summary_composer import SummaryComposer
from app.intelligence.reasoning.uncertainty_detector import UncertaintyDetector
from app.shared.enums import EvidencePolarity, GapSeverity, Intensity
from app.shared.models import (
    CandidateGap,
    CandidateGraph,
    CandidateReasoning,
    Evidence,
    ReasoningClaim,
    RoleDNA,
)

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


def _materiality(entity_ref: str, role: RoleDNA) -> Intensity:
    """Role-relative importance of a competency (mirrors Developer 4's mapping)."""
    if entity_ref in role.must_have_skills:
        return (
            Intensity.CRITICAL
            if role.coding_requirement in (Intensity.CRITICAL, Intensity.HIGH)
            else Intensity.HIGH
        )
    if entity_ref in role.nice_to_have_skills:
        return Intensity.LOW
    if role.domain and entity_ref == f"domain:{role.domain}":
        return Intensity.HIGH
    return Intensity.MEDIUM


def _strip_ref(ref: str) -> str:
    """'skill:python' -> 'python'; 'python' -> 'python' (for cross-convention matching)."""
    return ref.split(":", 1)[1] if ":" in ref else ref


def _role_ref_index(role: RoleDNA) -> dict[str, str]:
    """Map normalized skill name -> the role's exact ref string (bare or prefixed).

    RoleDNA refs and Evidence entity_refs can use different conventions (e.g. the
    blueprint provider emits bare ``python`` while Evidence emits ``skill:python``).
    Aligning claim entity_refs to the role's exact string lets Developer 4's gap
    analyzer — which matches by ``entity_ref in role.must_have_skills`` — work.
    """
    index: dict[str, str] = {}
    for ref in list(role.must_have_skills) + list(role.nice_to_have_skills):
        index[_strip_ref(ref).lower()] = ref
    return index


def _claims_from_evidence(evidence: list[Evidence], role: RoleDNA) -> list[ReasoningClaim]:
    """Synthesize one claim per entity from raw evidence (graph-disabled fallback).

    Deterministic and grounded in real evidence — no graph, no invented facts. Claim
    confidence follows Developer 4's corroboration shape (mean support confidence +
    source-diversity bonus - contradiction penalty). Claim entity_refs are aligned to
    the role's ref convention so gap/materiality matching works across conventions.
    """
    role_index = _role_ref_index(role)

    grouped: dict[str, dict[str, list[Evidence]]] = {}
    for ev in evidence:
        # Align to the role's exact ref string when this skill is a role requirement.
        ref = role_index.get(_strip_ref(ev.entity_ref).lower(), ev.entity_ref)
        bucket = grouped.setdefault(ref, {"supports": [], "contradicts": []})
        key = "contradicts" if ev.polarity == EvidencePolarity.CONTRADICTS else "supports"
        bucket[key].append(ev)

    claims: list[ReasoningClaim] = []
    for entity_ref, groups in sorted(grouped.items()):
        supports = groups["supports"]
        contradicts = groups["contradicts"]
        if not supports:
            continue
        confidences = [ev.confidence for ev in supports]
        base = sum(confidences) / len(confidences)
        sources = {ev.source for ev in supports}
        diversity = min(0.1, max(0, len(sources) - 1) * 0.04)
        penalty = min(0.25, len(contradicts) * 0.1)
        confidence = round(min(1.0, max(0.0, base + diversity - penalty)), 2)
        best = max(supports, key=lambda ev: ev.confidence)
        claims.append(
            ReasoningClaim(
                claim_id=f"claim_{entity_ref.replace(':', '_')}",
                statement=best.claim,
                entity_refs=[entity_ref],
                supporting_evidence_ids=[ev.evidence_id for ev in supports],
                counter_evidence_ids=[ev.evidence_id for ev in contradicts],
                confidence=confidence,
                materiality=_materiality(entity_ref, role),
                conclusion=(
                    f"Supported by {len(supports)} observation(s) across "
                    f"{len(sources)} source(s)."
                ),
            )
        )
    return claims


class ReasoningEngineAdapter:
    """Adapt Developer 4's ReasoningEngine to the v2 ``ReasoningEngine`` Protocol."""

    def __init__(self, engine: NativeReasoningEngine | None = None) -> None:
        self._engine = engine or NativeReasoningEngine()
        # Developer 4's own stateless sub-engines, reused for the graph-disabled path.
        self._gap_analyzer = GapAnalyzer()
        self._uncertainty_detector = UncertaintyDetector()
        self._confidence_engine = ConfidenceEngine()
        self._summary_composer = SummaryComposer()

    async def reason(self, graph: CandidateGraph, role: RoleDNA) -> CandidateReasoning:
        if graph.metadata.get("graph_disabled"):
            return self._reason_from_evidence(graph, role)
        result: ReasoningResult = self._engine.reason(graph, role)
        return self._to_candidate_reasoning(graph.candidate_id, role.job_id, result)

    def _reason_from_evidence(
        self, graph: CandidateGraph, role: RoleDNA
    ) -> CandidateReasoning:
        """Graph-disabled path: claims from evidence + Developer 4's own analyzers."""
        evidence = [
            Evidence.model_validate(raw) for raw in graph.metadata.get("evidence", [])
        ]
        claims = _claims_from_evidence(evidence, role)
        gaps = self._gap_analyzer.analyze(graph, role, claims)
        uncertainties = self._uncertainty_detector.detect(graph, role, claims, gaps)
        confidence = self._confidence_engine.compute(claims, gaps, uncertainties)
        summary = self._summary_composer.compose(claims, gaps, uncertainties, confidence)
        result = ReasoningResult(
            claims=claims,
            gaps=gaps,
            uncertainties=uncertainties,
            confidence=confidence,
            summary=summary,
        )
        reasoning = self._to_candidate_reasoning(graph.candidate_id, role.job_id, result)
        reasoning.metadata["reasoning_mode"] = "evidence_fallback"
        return reasoning

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
