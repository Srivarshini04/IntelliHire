"""FastAPI dependency providers for the v2 orchestration layer.

This module is the single composition root for the v2 runtime. Routes depend on the
*interfaces* declared in :mod:`app.shared.interfaces` and receive concrete wiring only
through these providers — no route, stage, or adapter instantiates another service
directly. When a real engine replaces an adapter (e.g. the Graph Intelligence
``CandidateGraphAdapter`` for ``NoOpGraphAdapter``), only this module changes.

Conversion lives exclusively in :mod:`app.runtime.adapters`; this module only wires.
"""

from __future__ import annotations

from app.intelligence.role_dna import BlueprintRoleDNAProvider
from app.runtime.adapters import (
    CandidateGraphAdapter,
    DecisionEngineAdapter,
    EvidenceProviderAdapter,
    NoOpFusionEngine,
    ReasoningEngineAdapter,
)
from app.runtime.candidate_evaluation_pipeline import CandidateEvaluationPipeline
from app.runtime.deterministic_ranking_engine import DeterministicRankingEngine
from app.runtime.ranking_orchestrator import RankingOrchestrator
from app.shared.enums import EvidenceSource
from app.shared.interfaces import (
    DecisionEngine,
    EvidenceProvider,
    FusionEngine,
    GraphBuilder,
    RankingEngine,
    ReasoningEngine,
    RoleDNAProvider,
)

# Evidence sources that have an adapter today (Developer 2's completed providers).
EVIDENCE_SOURCES: tuple[EvidenceSource, ...] = (
    EvidenceSource.RESUME,
    EvidenceSource.GITHUB,
    EvidenceSource.LINKEDIN,
    EvidenceSource.LEETCODE,
    EvidenceSource.PORTFOLIO,
)


# --------------------------------------------------------------------------- #
# Role side
# --------------------------------------------------------------------------- #
def get_role_dna_provider() -> RoleDNAProvider:
    """The deterministic blueprint -> RoleDNA enricher (owned module, ready now)."""
    return BlueprintRoleDNAProvider()


# --------------------------------------------------------------------------- #
# Candidate-side engines (each behind its shared interface)
# --------------------------------------------------------------------------- #
def get_evidence_provider(source: EvidenceSource) -> EvidenceProvider:
    """One EvidenceProviderAdapter for a single source (Developer 2 -> shared Evidence)."""
    return EvidenceProviderAdapter(source)


def get_evidence_providers() -> list[EvidenceProvider]:
    """One EvidenceProviderAdapter per supported source (Developer 2 -> shared Evidence)."""
    return [get_evidence_provider(source) for source in EVIDENCE_SOURCES]


def get_graph_builder() -> GraphBuilder:
    """Graph stage. Developer 3's Candidate Graph Intelligence, behind the async Protocol.

    ``CandidateGraphAdapter`` wraps Developer 3's synchronous ``GraphBuilder``. This is
    the single line that activates real graph intelligence; the runtime, routes, and
    pipeline are unchanged. (``NoOpGraphAdapter`` remains available as the graph-disabled
    fallback — swap it back here, and only here, to disable the graph.)
    """
    return CandidateGraphAdapter()


def get_fusion_engine() -> FusionEngine:
    """Fusion stage. No-op: confidence fusion happens inside the GraphBuilder.

    Developer 3's builder fuses per-node/edge confidence during ``build`` (a different
    abstraction from the pipeline ``FusionEngine``), so this stage stays a pass-through.
    """
    return NoOpFusionEngine()


def get_reasoning_engine() -> ReasoningEngine:
    """Developer 4's ReasoningEngine, adapted to the async shared Protocol."""
    return ReasoningEngineAdapter()


def get_decision_engine() -> DecisionEngine:
    """Developer 4's DecisionEngine, adapted to the async shared Protocol."""
    return DecisionEngineAdapter()


def get_ranking_engine() -> RankingEngine:
    """The active RankingEngine.

    Depend on this everywhere. ``DeterministicRankingEngine`` is registered here only
    as the default DI implementation (temporary ranking infrastructure; see
    docs/ranking-roadmap.md). A future engine replaces it through the same
    ``RankingEngine`` interface with no upstream change — the runtime never names the
    concrete implementation.
    """
    return DeterministicRankingEngine()


# Backward-compatible aliases (interface-typed). Prefer ``get_ranking_engine``.
get_deterministic_ranking_engine = get_ranking_engine


# --------------------------------------------------------------------------- #
# Composed runtime
# --------------------------------------------------------------------------- #
def get_candidate_evaluation_pipeline() -> CandidateEvaluationPipeline:
    """Assemble the per-candidate chain (Evidence -> Graph -> Fusion -> Reasoning -> Decision)."""
    return CandidateEvaluationPipeline(
        evidence_providers=get_evidence_providers(),
        graph_builder=get_graph_builder(),
        fusion_engine=get_fusion_engine(),
        reasoning_engine=get_reasoning_engine(),
        decision_engine=get_decision_engine(),
    )


def get_ranking_orchestrator() -> RankingOrchestrator:
    """Batch orchestration: per-candidate evaluation + rerank into a RankedList."""
    return RankingOrchestrator(
        evaluation_pipeline=get_candidate_evaluation_pipeline(),
        ranking_engine=get_ranking_engine(),
    )
