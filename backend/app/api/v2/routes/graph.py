"""Graph Intelligence APIs — build + query the Candidate Intelligence Graph.

POST /v2/graph/build runs the active ``GraphBuilder`` (Evidence -> ledger -> entity
resolution -> construction -> dedup -> inference -> fusion -> CandidateGraph) and
caches the result in the ``graph_registry``. The builder is supplied through
dependency injection (``get_graph_builder``) so this route never names a concrete
implementation. The GET routes answer the layer's target questions: what skills does
the candidate actually have, what evidence proves each, how strong is the confidence,
what projects/technologies connect, and what inferred capabilities exist beyond
explicit claims.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v2.schemas import (
    ERROR_RESPONSES,
    BuildGraphRequest,
    EntityConfidenceResponse,
    GraphSummaryResponse,
)
from app.intelligence.candidate_graph import (
    GraphReport,
    build_report,
    graph_registry,
)
from app.runtime.deps import get_graph_builder
from app.shared.enums import GraphNodeType
from app.shared.interfaces import GraphBuilder
from app.shared.models import CandidateGraph
from app.shared.models.evidence import EvidenceLedgerEntry
from app.shared.models.graph import GraphEdge, GraphNode

router = APIRouter(prefix="/graph", tags=["v2: graph"])


def _require_graph(graph_id: str) -> CandidateGraph:
    graph = graph_registry.get(graph_id)
    if graph is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": f"graph {graph_id!r} not found"},
        )
    return graph


@router.post(
    "/build",
    response_model=CandidateGraph,
    status_code=status.HTTP_200_OK,
    responses=ERROR_RESPONSES,
    summary="Build a CandidateGraph from Evidence",
    description=(
        "Assemble a candidate's Evidence into the unified CandidateGraph via the "
        "full intelligence pipeline (entity resolution, duplicate detection, "
        "relationship inference, confidence fusion). The active GraphBuilder is "
        "supplied via dependency injection (get_graph_builder); the server assigns "
        "the graph_id and caches the result for the query endpoints."
    ),
)
async def build_graph(
    payload: BuildGraphRequest,
    builder: GraphBuilder = Depends(get_graph_builder),
) -> CandidateGraph:
    graph = await builder.build(payload.candidate_id, payload.evidence, payload.job_id)
    graph_registry.put(graph)
    return graph


@router.get(
    "/candidate/{candidate_id}/latest",
    response_model=CandidateGraph,
    responses=ERROR_RESPONSES,
    summary="Fetch the latest CandidateGraph for a candidate",
)
async def latest_graph(candidate_id: str) -> CandidateGraph:
    graph = graph_registry.latest_for_candidate(candidate_id)
    if graph is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": f"no graph for candidate {candidate_id!r}"},
        )
    return graph


@router.get(
    "/{graph_id}",
    response_model=CandidateGraph,
    responses=ERROR_RESPONSES,
    summary="Fetch the complete candidate graph",
)
async def get_graph(graph_id: str) -> CandidateGraph:
    return _require_graph(graph_id)


@router.get(
    "/{graph_id}/report",
    response_model=GraphReport,
    responses=ERROR_RESPONSES,
    summary="UI-ready candidate intelligence report (skills, capabilities, projects)",
    description=(
        "Flatten the graph into render-ready sections for a candidate detail view: "
        "skills portfolio with confidence bands (green/yellow/red chip colours), "
        "inferred capabilities beyond explicit claims, projects with their "
        "technologies, experience, and a confidence summary."
    ),
)
async def get_report(graph_id: str) -> GraphReport:
    return build_report(_require_graph(graph_id))


@router.get(
    "/{graph_id}/summary",
    response_model=GraphSummaryResponse,
    responses=ERROR_RESPONSES,
    summary="Node/edge counts and inferred-capability overview",
)
async def get_summary(graph_id: str) -> GraphSummaryResponse:
    graph = _require_graph(graph_id)
    return GraphSummaryResponse(**graph_registry.summary(graph))


@router.get(
    "/{graph_id}/skills",
    response_model=list[GraphNode],
    responses=ERROR_RESPONSES,
    summary="Skills (and technologies) the candidate actually has, by confidence",
)
async def get_skills(graph_id: str) -> list[GraphNode]:
    return graph_registry.skills(_require_graph(graph_id))


@router.get(
    "/{graph_id}/projects",
    response_model=list[GraphNode],
    responses=ERROR_RESPONSES,
    summary="Projects and repositories supporting the candidate's claims",
)
async def get_projects(graph_id: str) -> list[GraphNode]:
    return graph_registry.projects(_require_graph(graph_id))


@router.get(
    "/{graph_id}/evidence",
    response_model=list[EvidenceLedgerEntry],
    responses=ERROR_RESPONSES,
    summary="Evidence proving the candidate — all, or for one entity via ?node_id=",
)
async def get_evidence(
    graph_id: str,
    node_id: str | None = Query(default=None, description="Restrict to one entity's evidence."),
) -> list[EvidenceLedgerEntry]:
    graph = _require_graph(graph_id)
    if node_id:
        return graph_registry.evidence_for_entity(graph, node_id)
    return list(graph.evidence_ledger)


@router.get(
    "/{graph_id}/confidence/{node_id}",
    response_model=EntityConfidenceResponse,
    responses=ERROR_RESPONSES,
    summary="Fused confidence + claim strength for one entity",
)
async def get_confidence(graph_id: str, node_id: str) -> EntityConfidenceResponse:
    graph = _require_graph(graph_id)
    node = graph.get_node(node_id)
    if node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": f"node {node_id!r} not in graph"},
        )
    return EntityConfidenceResponse(
        node_id=node.id,
        label=node.label,
        type=node.type,
        confidence=node.confidence,
        claim_strength=node.attributes.get("claim_strength"),
        source_count=node.attributes.get("source_count"),
        verification_status=node.attributes.get("verification_status"),
        evidence_count=len(node.evidence_ids),
        inferred=bool(node.attributes.get("inferred", False)),
    )


@router.get(
    "/{graph_id}/relationships",
    response_model=list[GraphEdge],
    responses=ERROR_RESPONSES,
    summary="Relationships in the graph — all, or touching one node via ?node_id=",
)
async def get_relationships(
    graph_id: str,
    node_id: str | None = Query(default=None, description="Restrict to edges on this node."),
) -> list[GraphEdge]:
    return graph_registry.relationships(_require_graph(graph_id), node_id)


@router.get(
    "/{graph_id}/query",
    response_model=list[GraphNode],
    responses=ERROR_RESPONSES,
    summary="Query nodes by skill/company/project name (substring), optional type filter",
)
async def query_nodes(
    graph_id: str,
    q: str = Query(..., min_length=1, description="Label/id substring to search for."),
    type: GraphNodeType | None = Query(default=None, description="Optional node-type filter."),
) -> list[GraphNode]:
    return graph_registry.find_nodes(_require_graph(graph_id), query=q, node_type=type)
