"""Synthesize recruiter-facing ReasoningClaim objects from complete graph inputs."""

from __future__ import annotations

from app.intelligence.reasoning.types import MaterialityMap
from app.shared.enums import EvidencePolarity, GraphEdgeType, GraphNodeType, Intensity
from app.shared.models import CandidateGraph, ReasoningClaim, RoleDNA
from app.shared.models.evidence import EvidenceLedgerEntry

_INTENSITY_RANK: tuple[Intensity, ...] = (
    Intensity.NONE,
    Intensity.LOW,
    Intensity.MEDIUM,
    Intensity.HIGH,
    Intensity.CRITICAL,
)

_RETRIEVAL_HINTS = ("retrieval", "embeddings", "vector_search", "vector")
_EVAL_HINTS = ("ranking_evaluation", "evaluation", "ndcg", "mrr")
_PYTHON_STACK = ("skill:python", "skill:fastapi")


def _max_intensity(values: list[Intensity]) -> Intensity:
    if not values:
        return Intensity.MEDIUM
    return max(values, key=lambda level: _INTENSITY_RANK.index(level))


def _materiality_for(entity_ref: str, materiality: MaterialityMap, role: RoleDNA) -> Intensity:
    """Resolve materiality from map or RoleDNA requirement lists (Decision B)."""
    if entity_ref in materiality.by_entity_ref:
        return materiality.by_entity_ref[entity_ref]
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


def _split_ledger(
    graph: CandidateGraph, node_id: str
) -> tuple[list[EvidenceLedgerEntry], list[EvidenceLedgerEntry]]:
    """Partition ledger entries for a node by polarity (Decision A)."""
    supports: list[EvidenceLedgerEntry] = []
    contradicts: list[EvidenceLedgerEntry] = []
    for entry in graph.evidence_for(node_id):
        if entry.polarity == EvidencePolarity.CONTRADICTS:
            contradicts.append(entry)
        else:
            supports.append(entry)
    return supports, contradicts


def _unique_evidence_ids(entries: list[EvidenceLedgerEntry]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for entry in entries:
        if entry.evidence_id not in seen:
            seen.add(entry.evidence_id)
            out.append(entry.evidence_id)
    return out


def _claim_confidence(
    supports: list[EvidenceLedgerEntry],
    contradicts: list[EvidenceLedgerEntry],
    node_confidence: float,
) -> float:
    """Derive claim confidence from corroboration and recorded contradictions."""
    if not supports and contradicts:
        base = sum(e.confidence for e in contradicts) / len(contradicts)
        return round(min(0.55, base * 0.75), 2)
    if supports:
        base = sum(e.confidence for e in supports) / len(supports)
        sources = {e.source for e in supports}
        diversity = min(0.1, max(0, len(sources) - 1) * 0.04)
        penalty = min(0.25, len(contradicts) * 0.1)
        return round(min(1.0, max(0.0, base + diversity - penalty)), 2)
    return round(min(1.0, max(0.0, node_confidence * 0.5)), 2)


def _outbound_targets(
    graph: CandidateGraph, source_id: str, *edge_types: GraphEdgeType
) -> list[str]:
    """Return target node ids for outbound edges of the given types (linear scan)."""
    allowed = set(edge_types)
    return [
        edge.target_id
        for edge in graph.edges
        if edge.source_id == source_id and edge.type in allowed
    ]


def _find_node_by_hint(graph: CandidateGraph, hints: tuple[str, ...]) -> list[str]:
    """Return node ids whose id or label matches any hint substring."""
    matched: list[str] = []
    for node in graph.nodes:
        key = f"{node.id} {node.label}".lower()
        if any(hint in key for hint in hints):
            matched.append(node.id)
    return matched


def _must_have_refs(role: RoleDNA) -> set[str]:
    return set(role.must_have_skills)


def _build_retrieval_claim(
    graph: CandidateGraph, materiality: MaterialityMap, role: RoleDNA
) -> ReasoningClaim | None:
    """Theme: production retrieval / hybrid search fit."""
    entity_refs: list[str] = []
    for node_id in _find_node_by_hint(graph, _RETRIEVAL_HINTS):
        if graph.get_node(node_id) and node_id not in entity_refs:
            entity_refs.append(node_id)

    candidate_id = next(
        (n.id for n in graph.nodes if n.type == GraphNodeType.CANDIDATE),
        None,
    )
    if candidate_id:
        for repo_id in _outbound_targets(graph, candidate_id, GraphEdgeType.BUILT):
            if repo_id not in entity_refs:
                entity_refs.append(repo_id)

    for skill_id in list(entity_refs):
        for repo_id in _outbound_targets(graph, skill_id, GraphEdgeType.USED_IN):
            if repo_id not in entity_refs:
                entity_refs.append(repo_id)

    if role.domain:
        domain_id = f"domain:{role.domain}"
        if graph.get_node(domain_id) and domain_id not in entity_refs:
            entity_refs.append(domain_id)

    if not entity_refs:
        return None

    supports: list[EvidenceLedgerEntry] = []
    contradicts: list[EvidenceLedgerEntry] = []
    confidences: list[float] = []
    for node_id in entity_refs:
        node = graph.get_node(node_id)
        if node is None:
            continue
        s, c = _split_ledger(graph, node_id)
        supports.extend(s)
        contradicts.extend(c)
        if node.confidence:
            confidences.append(node.confidence)

    if not supports:
        return None

    statement = _best_supporting_text(supports) or (
        "Demonstrates production-oriented retrieval or hybrid search experience."
    )

    mat = _max_intensity([_materiality_for(ref, materiality, role) for ref in entity_refs])
    confidence = _claim_confidence(supports, contradicts, max(confidences) if confidences else 0.0)

    return ReasoningClaim(
        claim_id="claim_retrieval",
        statement=statement,
        entity_refs=entity_refs,
        supporting_evidence_ids=_unique_evidence_ids(supports),
        counter_evidence_ids=_unique_evidence_ids(contradicts),
        confidence=confidence,
        materiality=mat,
        conclusion=(
            "Directly matches core role requirements for embeddings-based retrieval "
            "deployed beyond tutorial or toy projects."
        ),
    )


def _build_eval_claim(
    graph: CandidateGraph, materiality: MaterialityMap, role: RoleDNA
) -> ReasoningClaim | None:
    """Theme: ranking evaluation rigor (NDCG/MRR/A-B)."""
    candidates = [
        n
        for n in graph.nodes
        if n.type == GraphNodeType.SKILL
        and any(hint in n.id.lower() for hint in _EVAL_HINTS)
    ]
    if not candidates:
        return None

    must = _must_have_refs(role)
    node = next((n for n in candidates if n.id in must), candidates[0])
    supports, contradicts = _split_ledger(graph, node.id)
    if not supports:
        return None

    statement = _best_supporting_text(supports) or (
        f"Evaluates ranking systems with structured offline and online metrics ({node.label})."
    )

    return ReasoningClaim(
        claim_id="claim_eval",
        statement=statement,
        entity_refs=[node.id],
        supporting_evidence_ids=_unique_evidence_ids(supports),
        counter_evidence_ids=_unique_evidence_ids(contradicts),
        confidence=_claim_confidence(supports, contradicts, node.confidence),
        materiality=_materiality_for(node.id, materiality, role),
        conclusion=(
            "Satisfies explicit must-have expectations around designing evaluation "
            "frameworks for ranking systems."
        ),
    )


def _build_python_stack_claim(
    graph: CandidateGraph, materiality: MaterialityMap, role: RoleDNA
) -> ReasoningClaim | None:
    """Theme: Python + FastAPI corroboration across sources."""
    entity_refs = [ref for ref in _PYTHON_STACK if graph.get_node(ref)]
    if not entity_refs and not any("python" in ref for ref in _must_have_refs(role)):
        return None
    if not entity_refs:
        entity_refs = [
            n.id
            for n in graph.nodes_of_type(GraphNodeType.SKILL)
            if "python" in n.id.lower()
        ]
    if not entity_refs:
        return None

    supports: list[EvidenceLedgerEntry] = []
    contradicts: list[EvidenceLedgerEntry] = []
    for node_id in entity_refs:
        s, c = _split_ledger(graph, node_id)
        supports.extend(s)
        contradicts.extend(c)

    if not supports:
        return None

    return ReasoningClaim(
        claim_id="claim_python",
        statement=(
            "Strong Python with code-quality signal across assessment, contest, "
            "and production evidence."
        ),
        entity_refs=entity_refs,
        supporting_evidence_ids=_unique_evidence_ids(supports),
        counter_evidence_ids=_unique_evidence_ids(contradicts),
        confidence=_claim_confidence(supports, contradicts, 0.9),
        materiality=_max_intensity(
            [_materiality_for(ref, materiality, role) for ref in entity_refs]
        ),
        conclusion=(
            "Meets the strong Python and code-quality bar with corroborating multi-source signal."
        ),
    )


def _build_contradiction_claims(
    graph: CandidateGraph, materiality: MaterialityMap, role: RoleDNA
) -> list[ReasoningClaim]:
    """Emit dedicated claims for contradict-dominated skill nodes (Decision A)."""
    claims: list[ReasoningClaim] = []
    nice = set(role.nice_to_have_skills)

    for node in graph.nodes_of_type(GraphNodeType.SKILL):
        supports, contradicts = _split_ledger(graph, node.id)
        if not contradicts:
            continue
        if supports and len(supports) >= len(contradicts):
            continue

        counter_text = _best_supporting_text(contradicts) or node.label
        statement = f"Claims {node.label} but depth is unsubstantiated."
        if "self-listed" in counter_text.lower():
            statement = f"Claims {node.label} (self-listed) but depth is unsubstantiated."

        mat = _materiality_for(node.id, materiality, role)
        if node.id in nice:
            mat = Intensity.LOW

        conclusion = (
            "Nice-to-have only; the self-listed claim is contradicted by absence of "
            "corroborating projects, so do not credit depth. Not disqualifying."
            if node.id in nice
            else (
                "Recorded contradiction — down-weight this signal; verify in interview "
                "before crediting depth."
            )
        )

        claim_id = (
            "claim_finetuning"
            if node.id == "skill:llm_finetuning"
            else f"claim_contradict_{node.id.replace(':', '_')}"
        )

        claims.append(
            ReasoningClaim(
                claim_id=claim_id,
                statement=statement,
                entity_refs=[node.id],
                supporting_evidence_ids=[],
                counter_evidence_ids=_unique_evidence_ids(contradicts),
                confidence=_claim_confidence(supports, contradicts, node.confidence),
                materiality=mat,
                conclusion=conclusion,
            )
        )
    return claims


def _build_availability_claim(
    graph: CandidateGraph, materiality: MaterialityMap, role: RoleDNA
) -> ReasoningClaim | None:
    """Theme: sustained activity / reachability signals."""
    activity_nodes = [
        n
        for n in graph.nodes
        if n.type == GraphNodeType.CONTRIBUTION or n.id.startswith("activity:")
    ]
    if not activity_nodes:
        return None

    node = activity_nodes[0]
    supports, contradicts = _split_ledger(graph, node.id)
    if not supports:
        return None

    activity_score = node.attributes.get("github_activity_score")
    score_note = f" (activity score {activity_score})" if activity_score is not None else ""

    return ReasoningClaim(
        claim_id="claim_availability",
        statement=(
            "Shows sustained recent engineering activity and platform presence"
            f"{score_note}."
        ),
        entity_refs=[node.id],
        supporting_evidence_ids=_unique_evidence_ids(supports),
        counter_evidence_ids=_unique_evidence_ids(contradicts),
        confidence=_claim_confidence(supports, contradicts, node.confidence),
        materiality=materiality.by_theme.get("availability", Intensity.MEDIUM),
        conclusion=(
            "Recently active on engineering platforms — more reachable than "
            "perfect-on-paper-but-absent candidates."
        ),
    )


def _build_must_have_skill_claims(
    graph: CandidateGraph,
    materiality: MaterialityMap,
    role: RoleDNA,
    covered_refs: set[str],
) -> list[ReasoningClaim]:
    """Positive claims for remaining must-have skills not absorbed by themes."""
    claims: list[ReasoningClaim] = []
    for entity_ref in role.must_have_skills:
        if entity_ref in covered_refs:
            continue
        node = graph.get_node(entity_ref)
        if node is None:
            continue
        supports, contradicts = _split_ledger(graph, node.id)
        if not supports:
            continue

        claims.append(
            ReasoningClaim(
                claim_id=f"claim_{entity_ref.replace(':', '_')}",
                statement=_best_supporting_text(supports) or f"Demonstrates {node.label}.",
                entity_refs=[node.id],
                supporting_evidence_ids=_unique_evidence_ids(supports),
                counter_evidence_ids=_unique_evidence_ids(contradicts),
                confidence=_claim_confidence(supports, contradicts, node.confidence),
                materiality=_materiality_for(node.id, materiality, role),
                conclusion=f"Supports must-have requirement for {node.label}.",
            )
        )
    return claims


def _best_supporting_text(entries: list[EvidenceLedgerEntry]) -> str:
    if not entries:
        return ""
    return max(entries, key=lambda e: e.confidence).claim


class ClaimSynthesizer:
    """Form role-aware claims by reading the provided CandidateGraph as-is."""

    def synthesize(
        self,
        graph: CandidateGraph,
        materiality: MaterialityMap,
        role: RoleDNA,
    ) -> list[ReasoningClaim]:
        """Produce ReasoningClaim list for one (candidate, job) pair.

        Consumes ``graph.nodes``, ``graph.edges``, and ``graph.evidence_ledger``
        read-only via ``CandidateGraph`` traversal helpers. Does not mutate the
        graph or build persistent indexes.
        """
        if not graph.nodes:
            return []

        claims: list[ReasoningClaim] = []
        covered_refs: set[str] = set()

        themed_builders = (
            _build_retrieval_claim,
            _build_eval_claim,
            _build_python_stack_claim,
            _build_availability_claim,
        )
        for builder in themed_builders:
            claim = builder(graph, materiality, role)
            if claim is not None:
                claims.append(claim)
                covered_refs.update(claim.entity_refs)

        claims.extend(_build_must_have_skill_claims(graph, materiality, role, covered_refs))
        for claim in claims:
            covered_refs.update(claim.entity_refs)

        claims.extend(_build_contradiction_claims(graph, materiality, role))

        claims.sort(
            key=lambda c: (_INTENSITY_RANK.index(c.materiality), c.confidence),
            reverse=True,
        )
        return claims
