"""Detect missing or weak evidence for role competencies (Decision C).

Pure, read-only diff of CandidateGraph + ReasoningClaims against RoleDNA.
Does not rank, decide, summarize, or mutate inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.shared.enums import EvidencePolarity, Intensity
from app.shared.models import CandidateGraph, ReasoningClaim, RoleDNA

# Materiality thresholds (0..1) for gap bucketing.
_CRITICAL_MATERIALITY = 0.8
_MODERATE_MATERIALITY = 0.5
_STRONG_EVIDENCE_THRESHOLD = 0.6

_SEVERITY_ORDER = ("critical", "moderate", "minor")


@dataclass(frozen=True)
class GapItem:
    """One recruiter-facing absence or weakness signal."""

    category: str
    title: str
    severity: str
    rationale: str
    missing_evidence: list[str] = field(default_factory=list)


@dataclass
class GapAnalysis:
    """Structured gap output grouped by severity bucket."""

    critical: list[GapItem] = field(default_factory=list)
    moderate: list[GapItem] = field(default_factory=list)
    minor: list[GapItem] = field(default_factory=list)

    def all_items(self) -> list[GapItem]:
        return [*self.critical, *self.moderate, *self.minor]

    def total_count(self) -> int:
        return len(self.critical) + len(self.moderate) + len(self.minor)


def _materiality_score(entity_ref: str, role: RoleDNA) -> float:
    """Map a competency to a numeric materiality score from RoleDNA lists."""
    if entity_ref in role.must_have_skills:
        if role.coding_requirement in (Intensity.CRITICAL, Intensity.HIGH):
            return 0.9
        return 0.85
    if entity_ref in role.nice_to_have_skills:
        return 0.35
    if role.domain and entity_ref == f"domain:{role.domain}":
        return 0.7
    return 0.5


def _iter_competencies(role: RoleDNA) -> list[tuple[str, str]]:
    """Return (entity_ref, category) pairs in deterministic order without duplicates."""
    seen: set[str] = set()
    ordered: list[tuple[str, str]] = []

    for entity_ref in role.must_have_skills:
        if entity_ref not in seen:
            seen.add(entity_ref)
            ordered.append((entity_ref, "must_have"))

    for entity_ref in role.nice_to_have_skills:
        if entity_ref not in seen:
            seen.add(entity_ref)
            ordered.append((entity_ref, "nice_to_have"))

    if role.domain:
        domain_ref = f"domain:{role.domain}"
        if domain_ref not in seen:
            seen.add(domain_ref)
            ordered.append((domain_ref, "domain"))

    return sorted(ordered, key=lambda pair: pair[0])


def _claim_signal(entity_ref: str, claims: list[ReasoningClaim]) -> tuple[float, bool]:
    """Best positive claim confidence and whether only counter-evidence exists."""
    best_support = 0.0
    counter_only = False
    touched = False

    for claim in claims:
        if entity_ref not in claim.entity_refs:
            continue
        touched = True
        if claim.supporting_evidence_ids:
            best_support = max(best_support, claim.confidence)
        if claim.counter_evidence_ids and not claim.supporting_evidence_ids:
            counter_only = True

    if not touched:
        return 0.0, False
    return best_support, counter_only


def _evidence_strength(
    graph: CandidateGraph,
    entity_ref: str,
    claims: list[ReasoningClaim],
) -> float:
    """Estimate how well the graph (and claims) substantiate a competency."""
    claim_support, claim_counter_only = _claim_signal(entity_ref, claims)

    if claim_support >= _STRONG_EVIDENCE_THRESHOLD:
        return claim_support

    node = graph.get_node(entity_ref)

    if node is None:
        return 0.0

    supports = [
        entry
        for entry in graph.evidence_for(entity_ref)
        if entry.polarity == EvidencePolarity.SUPPORTS
    ]
    contradicts = [
        entry
        for entry in graph.evidence_for(entity_ref)
        if entry.polarity == EvidencePolarity.CONTRADICTS
    ]

    if not supports:
        if claim_support > 0.0:
            return claim_support
        if contradicts or claim_counter_only:
            return 0.2
        return 0.0

    avg_confidence = sum(entry.confidence for entry in supports) / len(supports)
    source_bonus = min(0.12, max(0, len(supports) - 1) * 0.04)
    ledger_strength = min(
        1.0,
        node.confidence * 0.55 + avg_confidence * 0.35 + source_bonus,
    )

    if contradicts and len(contradicts) >= len(supports):
        ledger_strength *= 0.45

    if claim_support:
        return min(1.0, max(ledger_strength, claim_support * 0.95))

    return ledger_strength


def _classify_severity(materiality: float, strength: float) -> str | None:
    """Return severity bucket or None when the competency is sufficiently covered."""
    if strength >= _STRONG_EVIDENCE_THRESHOLD:
        return None

    if materiality >= _CRITICAL_MATERIALITY:
        return "critical" if strength == 0.0 else "moderate"

    if materiality >= _MODERATE_MATERIALITY:
        return "moderate"

    return "minor"


def _title_for(entity_ref: str, graph: CandidateGraph) -> str:
    node = graph.get_node(entity_ref)
    if node is not None:
        return node.label
    if ":" in entity_ref:
        return entity_ref.split(":", 1)[1].replace("_", " ").title()
    return entity_ref


def _missing_evidence(
    graph: CandidateGraph,
    entity_ref: str,
    strength: float,
) -> list[str]:
    """Describe what evidence is absent or insufficient (deterministic, deduped)."""
    missing: list[str] = []
    seen: set[str] = set()

    def add(item: str) -> None:
        if item not in seen:
            seen.add(item)
            missing.append(item)

    node = graph.get_node(entity_ref)
    if node is None:
        add(entity_ref)
        return missing

    supports = [
        entry
        for entry in graph.evidence_for(entity_ref)
        if entry.polarity == EvidencePolarity.SUPPORTS
    ]
    contradicts = [
        entry
        for entry in graph.evidence_for(entity_ref)
        if entry.polarity == EvidencePolarity.CONTRADICTS
    ]

    if not supports:
        add(f"supporting_evidence:{entity_ref}")
    elif strength < _STRONG_EVIDENCE_THRESHOLD:
        add(f"corroboration:{entity_ref}")

    for entry in contradicts:
        add(entry.evidence_id)

    return missing


def _rationale(
    entity_ref: str,
    category: str,
    materiality: float,
    strength: float,
    severity: str,
) -> str:
    if strength == 0.0:
        return (
            f"Required {category.replace('_', ' ')} competency {entity_ref!r} has no "
            f"substantiating evidence in the candidate graph (materiality {materiality:.2f})."
        )
    if severity == "minor":
        return (
            f"Low-priority {category.replace('_', ' ')} competency {entity_ref!r} is weakly "
            f"covered (strength {strength:.2f})."
        )
    return (
        f"{category.replace('_', ' ').title()} competency {entity_ref!r} is present but "
        f"insufficiently corroborated (strength {strength:.2f}, materiality {materiality:.2f})."
    )


def _sort_items(items: list[GapItem]) -> list[GapItem]:
    return sorted(items, key=lambda item: (item.title.lower(), item.category, item.severity))


class GapAnalyzer:
    """Identify missing or weak evidence for important role requirements."""

    def analyze(
        self,
        graph: CandidateGraph,
        role: RoleDNA,
        claims: list[ReasoningClaim],
    ) -> GapAnalysis:
        """Diff RoleDNA competencies against graph evidence and synthesized claims.

        Read-only: does not mutate ``graph``, ``role``, or ``claims``.
        """
        analysis = GapAnalysis()
        seen_entities: set[str] = set()

        for entity_ref, category in _iter_competencies(role):
            if entity_ref in seen_entities:
                continue
            seen_entities.add(entity_ref)

            materiality = _materiality_score(entity_ref, role)
            strength = _evidence_strength(graph, entity_ref, claims)
            severity = _classify_severity(materiality, strength)
            if severity is None:
                continue

            item = GapItem(
                category=category,
                title=_title_for(entity_ref, graph),
                severity=severity,
                rationale=_rationale(entity_ref, category, materiality, strength, severity),
                missing_evidence=_missing_evidence(graph, entity_ref, strength),
            )

            if severity == "critical":
                analysis.critical.append(item)
            elif severity == "moderate":
                analysis.moderate.append(item)
            else:
                analysis.minor.append(item)

        analysis.critical = _sort_items(analysis.critical)
        analysis.moderate = _sort_items(analysis.moderate)
        analysis.minor = _sort_items(analysis.minor)
        return analysis
