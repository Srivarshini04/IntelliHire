"""FastAPI dependency providers for the v2 orchestration layer.

These are the single injection points the v2 API routes use. As the other
developers land their real engine implementations (EvidenceProvider, GraphBuilder,
FusionEngine, ReasoningEngine, DecisionEngine — and any production RankingEngine),
only this module needs to change; the routes stay put.
"""

from __future__ import annotations

from app.intelligence.role_dna import BlueprintRoleDNAProvider
from app.runtime.ranking_engine import BaselineRankingEngine
from app.shared.interfaces import RankingEngine, RoleDNAProvider


def get_role_dna_provider() -> RoleDNAProvider:
    """The deterministic blueprint -> RoleDNA enricher (owned module, ready now)."""
    return BlueprintRoleDNAProvider()


def get_ranking_engine() -> RankingEngine:
    """The deterministic baseline ranker (runtime infrastructure, ready now)."""
    return BaselineRankingEngine()
