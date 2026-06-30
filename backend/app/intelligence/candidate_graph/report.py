"""Graph report — a UI-ready projection of the CandidateGraph.

The CandidateGraph is the rich internal representation (typed nodes/edges, fused
confidence, evidence ledger). Frontends don't want to traverse a graph; they want
cards. ``build_report`` flattens the graph into the sections a candidate detail
view renders:

  * **skills_portfolio** — every skill/technology with its fused confidence, a
    green/yellow/red band (the chip colour), how many proofs back it, which
    sources, and whether it was proven or merely inferred.
  * **inferred_capabilities** — DOMAIN nodes the inference engine derived (e.g.
    "Backend Development" from FastAPI + Python) — the layer's signature output.
  * **projects** — projects/repositories with the technologies they use.
  * **experience** — organizations worked at, with any inferred domain.
  * **confidence_summary** — green/yellow/red counts for an at-a-glance bar.

This is a read-only projection: it adds no new facts, only reshapes the graph.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.shared.constants import CONFIDENCE_GREEN_THRESHOLD, CONFIDENCE_YELLOW_THRESHOLD
from app.shared.enums import ConfidenceLevel, GraphEdgeType, GraphNodeType
from app.shared.models.graph import CandidateGraph, GraphNode


def confidence_band(confidence: float) -> ConfidenceLevel:
    """Map a fused confidence to the chip colour band."""
    if confidence > CONFIDENCE_GREEN_THRESHOLD:
        return ConfidenceLevel.GREEN
    if confidence >= CONFIDENCE_YELLOW_THRESHOLD:
        return ConfidenceLevel.YELLOW
    return ConfidenceLevel.RED


# --- report sections ----------------------------------------------------------
class SkillEntry(BaseModel):
    node_id: str
    name: str
    confidence: float = Field(ge=0.0, le=1.0)
    level: ConfidenceLevel = Field(description="green/yellow/red chip colour.")
    proven_by: int = Field(description="Number of evidence items supporting this skill.")
    sources: list[str] = Field(default_factory=list, description="Distinct attesting sources.")
    claim_strength: float | None = None
    inferred: bool = Field(default=False, description="Derived, not explicitly claimed.")
    proven_by_artifacts: list[str] = Field(
        default_factory=list, description="Project/repo names that demonstrate this skill."
    )


class CapabilityEntry(BaseModel):
    node_id: str
    name: str
    confidence: float = Field(ge=0.0, le=1.0)
    level: ConfidenceLevel
    derived_from: list[str] = Field(
        default_factory=list, description="Technologies/orgs the capability was inferred from."
    )


class ProjectEntry(BaseModel):
    node_id: str
    name: str
    type: GraphNodeType
    confidence: float = Field(ge=0.0, le=1.0)
    level: ConfidenceLevel
    technologies: list[str] = Field(default_factory=list)
    evidence_count: int = 0


class ExperienceEntry(BaseModel):
    node_id: str
    organization: str
    confidence: float = Field(ge=0.0, le=1.0)
    level: ConfidenceLevel
    domain: str | None = None


class GraphReport(BaseModel):
    """The full UI-ready candidate intelligence report."""

    graph_id: str
    candidate_id: str
    job_id: str | None = None
    node_count: int
    edge_count: int
    evidence_count: int
    skills_portfolio: list[SkillEntry] = Field(default_factory=list)
    inferred_capabilities: list[CapabilityEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    confidence_summary: dict[str, int] = Field(default_factory=dict)


def build_report(graph: CandidateGraph) -> GraphReport:
    """Flatten a CandidateGraph into UI-ready report sections."""
    # source map: node_id -> distinct evidence sources (from the bound ledger).
    sources_by_node: dict[str, list[str]] = {}
    for entry in graph.evidence_ledger:
        bucket = sources_by_node.setdefault(entry.supporting_node_id, [])
        if entry.source.value not in bucket:
            bucket.append(entry.source.value)

    label = {n.id: n.label for n in graph.nodes}

    # outbound technology/skill names per artefact (for project tech lists + skill proofs).
    uses: dict[str, list[str]] = {}
    proves_skill_to_artifacts: dict[str, list[str]] = {}
    domain_sources: dict[str, list[str]] = {}
    for e in graph.edges:
        if e.type == GraphEdgeType.USES:
            uses.setdefault(e.source_id, []).append(label.get(e.target_id, e.target_id))
        elif e.type == GraphEdgeType.PROVES:
            proves_skill_to_artifacts.setdefault(e.target_id, []).append(
                label.get(e.source_id, e.source_id)
            )
        elif e.type == GraphEdgeType.IN_DOMAIN and not e.source_id.startswith("candidate:"):
            # The candidate->domain edge marks the capability; the *evidence* for it
            # is the technology/org that implies the domain, so skip the candidate.
            domain_sources.setdefault(e.target_id, []).append(
                label.get(e.source_id, e.source_id)
            )

    skills: list[SkillEntry] = []
    for n in _nodes(graph, GraphNodeType.SKILL, GraphNodeType.TECHNOLOGY):
        skills.append(
            SkillEntry(
                node_id=n.id,
                name=n.label,
                confidence=n.confidence,
                level=confidence_band(n.confidence),
                proven_by=len(n.evidence_ids),
                sources=sources_by_node.get(n.id, []),
                claim_strength=n.attributes.get("claim_strength"),
                inferred=bool(n.attributes.get("inferred", False)) and not n.evidence_ids,
                proven_by_artifacts=sorted(set(proves_skill_to_artifacts.get(n.id, []))),
            )
        )
    skills.sort(key=lambda s: s.confidence, reverse=True)

    capabilities = [
        CapabilityEntry(
            node_id=n.id,
            name=n.label,
            confidence=n.confidence,
            level=confidence_band(n.confidence),
            derived_from=sorted(set(domain_sources.get(n.id, []))),
        )
        for n in _nodes(graph, GraphNodeType.DOMAIN)
    ]
    capabilities.sort(key=lambda c: c.confidence, reverse=True)

    projects = [
        ProjectEntry(
            node_id=n.id,
            name=n.label,
            type=n.type,
            confidence=n.confidence,
            level=confidence_band(n.confidence),
            technologies=sorted(set(uses.get(n.id, []))),
            evidence_count=len(n.evidence_ids),
        )
        for n in _nodes(graph, GraphNodeType.PROJECT, GraphNodeType.REPOSITORY)
    ]

    # organization -> first inferred domain, if any.
    org_domain: dict[str, str] = {}
    for e in graph.edges:
        if e.type == GraphEdgeType.IN_DOMAIN and e.source_id.startswith("org:"):
            org_domain.setdefault(e.source_id, label.get(e.target_id, e.target_id))
    experience = [
        ExperienceEntry(
            node_id=n.id,
            organization=n.label,
            confidence=n.confidence,
            level=confidence_band(n.confidence),
            domain=org_domain.get(n.id),
        )
        for n in _nodes(graph, GraphNodeType.ORGANIZATION)
    ]

    summary = {"green": 0, "yellow": 0, "red": 0}
    for s in skills:
        summary[s.level.value] += 1

    return GraphReport(
        graph_id=graph.graph_id,
        candidate_id=graph.candidate_id,
        job_id=graph.job_id,
        node_count=len(graph.nodes),
        edge_count=len(graph.edges),
        evidence_count=len(graph.evidence_ledger),
        skills_portfolio=skills,
        inferred_capabilities=capabilities,
        projects=projects,
        experience=experience,
        confidence_summary=summary,
    )


def _nodes(graph: CandidateGraph, *types: GraphNodeType) -> list[GraphNode]:
    out: list[GraphNode] = []
    for t in types:
        out.extend(graph.nodes_of_type(t))
    return out
