"""Detect epistemic uncertainty from graph evidence, claims, and gap signals.

Pure read-only reasoning — no ranking, decisions, confidence scoring, or mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.intelligence.reasoning.gap_analyzer import GapAnalysis, GapItem
from app.shared.enums import EvidencePolarity, Intensity
from app.shared.models import CandidateGraph, ReasoningClaim, RoleDNA

_HIGH_MATERIALITY = 0.8
_MODERATE_MATERIALITY = 0.5
_WEAK_CONFIDENCE = 0.65
_STRONG_CLAIM_CONFIDENCE = 0.75
_MIN_CORROBORATING_SOURCES = 2

_SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}


@dataclass(frozen=True)
class UncertaintyItem:
    """One honest limit on what the evidence supports."""

    category: str
    title: str
    severity: str
    rationale: str
    related_entities: list[str] = field(default_factory=list)
    evidence_count: int = 0


@dataclass
class UncertaintyAnalysis:
    """Structured uncertainty output grouped by severity bucket."""

    high: list[UncertaintyItem] = field(default_factory=list)
    medium: list[UncertaintyItem] = field(default_factory=list)
    low: list[UncertaintyItem] = field(default_factory=list)

    def all_items(self) -> list[UncertaintyItem]:
        return [*self.high, *self.medium, *self.low]

    def total_count(self) -> int:
        return len(self.high) + len(self.medium) + len(self.low)


def _materiality_score(entity_ref: str, role: RoleDNA) -> float:
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


def _title_for(entity_ref: str, graph: CandidateGraph) -> str:
    node = graph.get_node(entity_ref)
    if node is not None:
        return node.label
    if ":" in entity_ref:
        return entity_ref.split(":", 1)[1].replace("_", " ").title()
    return entity_ref


def _ledger_for(graph: CandidateGraph, entity_ref: str) -> list:
    return graph.evidence_for(entity_ref)


def _supports(graph: CandidateGraph, entity_ref: str) -> list:
    return [
        entry
        for entry in _ledger_for(graph, entity_ref)
        if entry.polarity == EvidencePolarity.SUPPORTS
    ]


def _contradicts(graph: CandidateGraph, entity_ref: str) -> list:
    return [
        entry
        for entry in _ledger_for(graph, entity_ref)
        if entry.polarity == EvidencePolarity.CONTRADICTS
    ]


def _evidence_count(graph: CandidateGraph, entity_refs: list[str]) -> int:
    return sum(len(_ledger_for(graph, entity_ref)) for entity_ref in entity_refs)


def _is_well_supported(
    graph: CandidateGraph,
    entity_ref: str,
    claims: list[ReasoningClaim],
) -> bool:
    """Return True when independent sources agree with strong, consistent evidence."""
    supports = _supports(graph, entity_ref)
    contradicts = _contradicts(graph, entity_ref)
    if contradicts:
        return False

    sources = {entry.source for entry in supports}
    if (
        len(sources) >= _MIN_CORROBORATING_SOURCES
        and supports
        and all(entry.confidence >= _WEAK_CONFIDENCE for entry in supports)
    ):
        return True

    for claim in claims:
        if entity_ref not in claim.entity_refs:
            continue
        if (
            len(claim.supporting_evidence_ids) >= _MIN_CORROBORATING_SOURCES
            and claim.confidence >= _STRONG_CLAIM_CONFIDENCE
            and not claim.counter_evidence_ids
        ):
            return True

    node = graph.get_node(entity_ref)
    if (
        node is not None
        and len(supports) >= _MIN_CORROBORATING_SOURCES
        and node.confidence >= _STRONG_CLAIM_CONFIDENCE
    ):
        return True

    return False


def _make_item(
    *,
    category: str,
    title: str,
    severity: str,
    rationale: str,
    related_entities: list[str],
    graph: CandidateGraph,
) -> UncertaintyItem:
    return UncertaintyItem(
        category=category,
        title=title,
        severity=severity,
        rationale=rationale,
        related_entities=related_entities,
        evidence_count=_evidence_count(graph, related_entities),
    )


def _detect_missing_evidence(
    graph: CandidateGraph,
    role: RoleDNA,
    claims: list[ReasoningClaim],
) -> list[UncertaintyItem]:
    items: list[UncertaintyItem] = []

    for entity_ref, category in _iter_competencies(role):
        if _is_well_supported(graph, entity_ref, claims):
            continue

        supports = _supports(graph, entity_ref)
        materiality = _materiality_score(entity_ref, role)
        node = graph.get_node(entity_ref)

        if supports or (node is not None and node.confidence >= _WEAK_CONFIDENCE):
            continue

        if materiality < _HIGH_MATERIALITY:
            continue

        items.append(
            _make_item(
                category="missing_evidence",
                title=_title_for(entity_ref, graph),
                severity="high",
                rationale=(
                    f"No supporting evidence found for high-materiality competency "
                    f"{entity_ref!r} ({category.replace('_', ' ')})."
                ),
                related_entities=[entity_ref],
                graph=graph,
            )
        )

    return items


def _detect_conflicts(
    graph: CandidateGraph,
    claims: list[ReasoningClaim],
) -> list[UncertaintyItem]:
    items: list[UncertaintyItem] = []
    seen: set[str] = set()

    for node in graph.nodes:
        entity_ref = node.id
        if entity_ref in seen:
            continue

        supports = _supports(graph, entity_ref)
        contradicts = _contradicts(graph, entity_ref)
        claim_conflict = any(
            claim.supporting_evidence_ids and claim.counter_evidence_ids
            for claim in claims
            if entity_ref in claim.entity_refs
        )

        if not ((supports and contradicts) or claim_conflict):
            continue

        seen.add(entity_ref)
        items.append(
            _make_item(
                category="conflicting_evidence",
                title=_title_for(entity_ref, graph),
                severity="high",
                rationale=(
                    f"Conflicting evidence recorded for {entity_ref!r}: "
                    f"{len(supports)} supporting and {len(contradicts)} contradicting entries."
                ),
                related_entities=[entity_ref],
                graph=graph,
            )
        )

    return items


def _detect_weak_evidence(
    graph: CandidateGraph,
    role: RoleDNA,
    claims: list[ReasoningClaim],
) -> list[UncertaintyItem]:
    items: list[UncertaintyItem] = []

    for entity_ref, category in _iter_competencies(role):
        if _is_well_supported(graph, entity_ref, claims):
            continue

        supports = _supports(graph, entity_ref)
        if not supports:
            continue

        if _contradicts(graph, entity_ref):
            continue

        sources = {entry.source for entry in supports}
        avg_confidence = sum(entry.confidence for entry in supports) / len(supports)
        node = graph.get_node(entity_ref)
        node_confidence = node.confidence if node else avg_confidence

        is_weak = len(supports) == 1 and avg_confidence < _WEAK_CONFIDENCE
        is_weak = is_weak or node_confidence < 0.55

        if not is_weak:
            continue

        materiality = _materiality_score(entity_ref, role)
        severity = "medium" if materiality >= _MODERATE_MATERIALITY else "low"

        items.append(
            _make_item(
                category="weak_evidence",
                title=_title_for(entity_ref, graph),
                severity=severity,
                rationale=(
                    f"Only weak evidence supports {entity_ref!r} "
                    f"(avg confidence {avg_confidence:.2f}, {len(sources)} source(s))."
                ),
                related_entities=[entity_ref],
                graph=graph,
            )
        )

    return items


def _detect_sparse_evidence(
    graph: CandidateGraph,
    role: RoleDNA,
    claims: list[ReasoningClaim],
) -> list[UncertaintyItem]:
    items: list[UncertaintyItem] = []

    for entity_ref, category in _iter_competencies(role):
        if _is_well_supported(graph, entity_ref, claims):
            continue

        supports = _supports(graph, entity_ref)
        if len(supports) != 1:
            continue

        if _contradicts(graph, entity_ref):
            continue

        materiality = _materiality_score(entity_ref, role)
        if materiality < _MODERATE_MATERIALITY:
            continue

        avg_confidence = supports[0].confidence
        if avg_confidence < _WEAK_CONFIDENCE:
            continue

        items.append(
            _make_item(
                category="sparse_evidence",
                title=_title_for(entity_ref, graph),
                severity="medium",
                rationale=(
                    f"Sparse corroboration for important competency {entity_ref!r}: "
                    f"only one supporting observation ({category.replace('_', ' ')})."
                ),
                related_entities=[entity_ref],
                graph=graph,
            )
        )

    return items


def _gap_entities(gap: GapItem) -> list[str]:
    entities = [item for item in gap.missing_evidence if ":" in item and not item.startswith("supporting_")]
    if entities:
        return entities
    return [gap.title]


def _detect_gap_uncertainty(
    graph: CandidateGraph,
    gaps: GapAnalysis,
) -> list[UncertaintyItem]:
    items: list[UncertaintyItem] = []

    mapping: tuple[tuple[str, list[GapItem]], ...] = (
        ("high", gaps.critical),
        ("medium", gaps.moderate),
        ("low", gaps.minor),
    )

    for severity, gap_items in mapping:
        for gap in gap_items:
            related = _gap_entities(gap)
            items.append(
                _make_item(
                    category="gap",
                    title=gap.title,
                    severity=severity,
                    rationale=f"GapAnalyzer reported {gap.severity} gap: {gap.rationale}",
                    related_entities=related,
                    graph=graph,
                )
            )

    return items


def _dedupe_items(items: list[UncertaintyItem]) -> list[UncertaintyItem]:
    """Keep the highest-severity item per related-entity set."""
    best: dict[tuple[str, ...], UncertaintyItem] = {}

    for item in items:
        key = tuple(sorted(item.related_entities)) or (item.title.lower(),)
        current = best.get(key)
        if current is None or _SEVERITY_RANK[item.severity] > _SEVERITY_RANK[current.severity]:
            best[key] = item

    return list(best.values())


def _sort_uncertainties(items: list[UncertaintyItem]) -> list[UncertaintyItem]:
    return sorted(
        items,
        key=lambda item: (item.title.lower(), item.category, item.severity),
    )


class UncertaintyDetector:
    """Identify areas where evidence is insufficient, conflicting, or incomplete."""

    def detect(
        self,
        graph: CandidateGraph,
        role: RoleDNA,
        claims: list[ReasoningClaim],
        gaps: GapAnalysis,
    ) -> UncertaintyAnalysis:
        """Return structured uncertainties without mutating inputs."""
        candidates: list[UncertaintyItem] = []
        candidates.extend(_detect_missing_evidence(graph, role, claims))
        candidates.extend(_detect_conflicts(graph, claims))
        candidates.extend(_detect_weak_evidence(graph, role, claims))
        candidates.extend(_detect_sparse_evidence(graph, role, claims))
        candidates.extend(_detect_gap_uncertainty(graph, gaps))

        deduped = _dedupe_items(candidates)
        analysis = UncertaintyAnalysis()

        for item in _sort_uncertainties(deduped):
            if item.severity == "high":
                analysis.high.append(item)
            elif item.severity == "medium":
                analysis.medium.append(item)
            else:
                analysis.low.append(item)

        return analysis
