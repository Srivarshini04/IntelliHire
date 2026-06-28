"""FastAPI dependency providers for the v2 orchestration layer.

These are the single injection points the v2 API routes use. As the other
developers land their real engine implementations (EvidenceProvider, GraphBuilder,
FusionEngine, ReasoningEngine, DecisionEngine — and any production RankingEngine),
only this module needs to change; the routes stay put.
"""

from __future__ import annotations

from app.intelligence.role_dna import BlueprintRoleDNAProvider
from app.runtime.deterministic_ranking_engine import DeterministicRankingEngine
from app.shared.interfaces import RankingEngine, RoleDNAProvider


def get_role_dna_provider() -> RoleDNAProvider:
    """The deterministic blueprint -> RoleDNA enricher (owned module, ready now)."""
    return BlueprintRoleDNAProvider()


def get_deterministic_ranking_engine() -> RankingEngine:
    """Inject the DeterministicRankingEngine — temporary ranking INFRASTRUCTURE.

    This is not DELULU's production ranking algorithm; it provides stable,
    deterministic ordering so the pipeline + API function today. A real engine
    (see docs/ranking-roadmap.md) replaces it through the same RankingEngine
    interface with no upstream change.
    """
    return DeterministicRankingEngine()


# Backward-compatible alias — the HTTP API is unchanged; this provider currently
# injects the deterministic implementation. Prefer get_deterministic_ranking_engine().
get_ranking_engine = get_deterministic_ranking_engine
