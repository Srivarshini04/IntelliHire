"""Anti-corruption adapter layer — the ONLY translation boundary in the v2 runtime.

The runtime, API routes and dependency injection speak *only* the shared contracts
(``app.shared.models`` / ``app.shared.interfaces``). The developers' existing
implementations speak their own shapes. These adapters are the single place where
the two vocabularies meet: every model conversion happens here and nowhere else.

    Shared contracts  <--[ adapters ]-->  legacy implementations

Rules enforced by this package:
  * All model conversions live inside adapters.
  * Runtime stages never convert.
  * API routes never convert.
  * Dependency injection never converts.
  * Shared contracts are untouched.
  * Developer implementations are untouched.

Adapters:
  * EvidenceProviderAdapter — Developer 2 evidence sources -> EvidenceProvider Protocol.
  * NoOpGraphAdapter        — GraphBuilder placeholder while Developer 3 is absent.
  * NoOpFusionEngine        — FusionEngine no-op (graph disabled; required by FusionStage).
  * ReasoningEngineAdapter  — Developer 4 sync ReasoningEngine -> ReasoningEngine Protocol.
  * DecisionEngineAdapter   — Developer 4 sync DecisionEngine -> DecisionEngine Protocol.
"""

from __future__ import annotations

from app.runtime.adapters.decision_adapter import DecisionEngineAdapter
from app.runtime.adapters.evidence_adapter import EvidenceProviderAdapter
from app.runtime.adapters.noop_graph_adapter import NoOpFusionEngine, NoOpGraphAdapter
from app.runtime.adapters.reasoning_adapter import ReasoningEngineAdapter

__all__ = [
    "EvidenceProviderAdapter",
    "NoOpGraphAdapter",
    "NoOpFusionEngine",
    "ReasoningEngineAdapter",
    "DecisionEngineAdapter",
]
