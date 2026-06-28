"""Pipeline interfaces (Protocols) for DELULU v2 — contracts only, no logic.

Every stage is a Protocol with typed inputs/outputs and an async signature so the
orchestrator can ``await`` uniformly (even where an implementation is pure-compute).
The orchestrator wires these together via ``app.shared.context.PipelineContext``.

Stage order:
    EvidenceProvider* -> GraphBuilder -> FusionEngine -> ReasoningEngine
    -> DecisionEngine -> RankingEngine     (RoleDNAProvider feeds the role side)
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.shared.constants import DEFAULT_RETRIEVAL_TOP_K, SUBMISSION_SIZE
from app.shared.enums import EvidenceSource
from app.shared.models import (
    CandidateGraph,
    CandidateRanking,
    CandidateReasoning,
    Evidence,
    HiringDecision,
    RankedList,
    RoleDNA,
)


@runtime_checkable
class EvidenceProvider(Protocol):
    """Turn one raw source into atomic Evidence.

    Input:  candidate_id, raw source payload (dict).
    Output: list[Evidence] (observed facts only — never absence; no role weighting).
    Responsibility: parse/normalize a single source and emit canonical-entity claims.
    """

    source: EvidenceSource

    async def collect(self, candidate_id: str, raw: dict[str, Any]) -> list[Evidence]: ...


@runtime_checkable
class RoleDNAProvider(Protocol):
    """Derive rich hiring intent from a job.

    Input:  job_id, optional raw JD text, optional RoleBlueprint dict.
    Output: RoleDNA.
    Responsibility: infer explicit + latent role requirements (the 'question'
    reasoning answers). No candidate data involved.
    """

    async def build(
        self, job_id: str, jd_text: str | None = None, blueprint: dict[str, Any] | None = None
    ) -> RoleDNA: ...


@runtime_checkable
class GraphBuilder(Protocol):
    """Assemble Evidence into a CandidateGraph.

    Input:  candidate_id, list[Evidence], optional job_id.
    Output: CandidateGraph (nodes, edges, evidence_ledger).
    Responsibility: canonicalize entities (entity_resolver), create nodes/edges,
    write the EvidenceLedger. Deterministic; no scoring.
    """

    async def build(
        self, candidate_id: str, evidence: list[Evidence], job_id: str | None = None
    ) -> CandidateGraph: ...


@runtime_checkable
class FusionEngine(Protocol):
    """Collapse multi-source evidence into one fused confidence per node.

    Input:  CandidateGraph.
    Output: CandidateGraph with GraphNode.confidence populated.
    Responsibility: monotonic probability-of-support fusion over SUPPORTS evidence
    (DECISION A). Contradictions are recorded for reasoning, never subtracted.
    """

    async def fuse(self, graph: CandidateGraph) -> CandidateGraph: ...


@runtime_checkable
class ReasoningEngine(Protocol):
    """Reason over (CandidateGraph + RoleDNA).

    Input:  CandidateGraph, RoleDNA.
    Output: CandidateReasoning (claims, counter-evidence, gaps, uncertainties).
    Responsibility: the moat. Resolve contradictions, compute role-relative
    materiality (DECISION B), detect absent-but-required signals (DECISION C).
    """

    async def reason(self, graph: CandidateGraph, role: RoleDNA) -> CandidateReasoning: ...


@runtime_checkable
class DecisionEngine(Protocol):
    """Turn reasoning into a recruiter-facing decision.

    Input:  CandidateReasoning, RoleDNA.
    Output: HiringDecision (recommendation, reasons, reservations, interview focus,
            and a derived numeric score).
    Responsibility: synthesize a defensible decision; the score is a projection of
    the reasoning, not its source.
    """

    async def decide(self, reasoning: CandidateReasoning, role: RoleDNA) -> HiringDecision: ...


@runtime_checkable
class RankingEngine(Protocol):
    """Two-stage ranker (100k -> top 100).

    retrieve() — STAGE 1: cheap, deterministic, vectorized scoring over the FULL
        candidate pool. No LLM. Returns a shortlist worth reasoning about.
        Input:  job_id, RoleDNA, list of raw candidate dicts, top_k.
        Output: list[CandidateRanking] (stage=RETRIEVAL).

    rerank() — STAGE 2: fine ranking over the shortlist from HiringDecisions.
        Input:  job_id, list[HiringDecision], limit.
        Output: RankedList (stage=RERANK) — the submitted rows incl. `reasoning`.
    """

    async def retrieve(
        self,
        job_id: str,
        role: RoleDNA,
        candidates: list[dict[str, Any]],
        top_k: int = DEFAULT_RETRIEVAL_TOP_K,
    ) -> list[CandidateRanking]: ...

    async def rerank(
        self, job_id: str, decisions: list[HiringDecision], limit: int = SUBMISSION_SIZE
    ) -> RankedList: ...
