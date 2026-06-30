# DELULU v2 — Runtime Execution Contract

The canonical reference for the v2 runtime. For each stage of the required pipeline:
input type, output type, the shared interface it speaks, the concrete implementation, the
adapter that bridges it (if any), and the DI provider that supplies it.

**Required pipeline:** JD → Role Blueprint → **Role DNA** → **Evidence** → *Evidence
Normalization* → **NoOpGraph** → *Fusion (no-op)* → **Reasoning** → **Decision** →
**Ranking** → *Explainability* → API Response.

All types are from `app.shared.models`; all interfaces from `app.shared.interfaces`; all
adapters from `app.runtime.adapters`; all DI providers from `app.runtime.deps`. The
runtime/stages/routes speak **only** shared types — every conversion is inside an adapter.

---

## Stage-by-stage contract

### 1. Role DNA
| Aspect | Value |
|---|---|
| Input | `job_id: str`, `jd_text: str \| None`, `blueprint: dict \| None` |
| Output | `RoleDNA` |
| Shared interface | `RoleDNAProvider.build(...)` (async) |
| Concrete impl | `app.intelligence.role_dna.BlueprintRoleDNAProvider` |
| Adapter | none — native conforms to the Protocol |
| DI provider | `deps.get_role_dna_provider()` |
| Notes | Role side. Derives must/nice skills, materiality inputs. Independent of candidate data. |

### 2. Evidence (incl. Evidence Normalization)
| Aspect | Value |
|---|---|
| Input | `candidate_id: str`, `raw: dict[str, Any]` (one source payload) |
| Output | `list[Evidence]` |
| Shared interface | `EvidenceProvider.collect(...)` (async), `source: EvidenceSource` |
| Concrete impl | Developer 2 `app.services.evidence.normalizer.normalize()` → `EvidenceObject` |
| Adapter | `EvidenceProviderAdapter` (one per `EvidenceSource`) |
| DI provider | `deps.get_evidence_providers()` → `list[EvidenceProvider]` |
| Notes | *Normalization* (dict→`EvidenceObject`) is Dev 2's `normalize`; the adapter then converts `EvidenceObject`→`Evidence`. Failed/empty source → `[]` (DECISION C). Stage runs all providers concurrently (`EvidenceStage`, `asyncio.gather`). |

### 3. Graph (skipped)
| Aspect | Value |
|---|---|
| Input | `candidate_id: str`, `evidence: list[Evidence]`, `job_id: str \| None` |
| Output | `CandidateGraph` (empty topology; `metadata.graph_disabled=True`, `metadata.evidence=[...]`) |
| Shared interface | `GraphBuilder.build(...)` (async) |
| Concrete impl | **none** — Graph Intelligence (Developer 3) not implemented |
| Adapter | `NoOpGraphAdapter` (passthrough + telemetry; builds no nodes) |
| DI provider | `deps.get_graph_builder()` |
| Notes | Drop-in slot for the future `CandidateGraphAdapter` — zero runtime/API change. |

### 4. Fusion (no-op)
| Aspect | Value |
|---|---|
| Input | `CandidateGraph` |
| Output | `CandidateGraph` (unchanged; `metadata.fusion_stage="skipped"`) |
| Shared interface | `FusionEngine.fuse(...)` (async) |
| Concrete impl | **none** — part of Developer 3's graph intelligence |
| Adapter | `NoOpFusionEngine` |
| DI provider | `deps.get_fusion_engine()` |
| Notes | Present so the frozen `FusionStage` runs unchanged; nothing to fuse on an empty graph. |

### 5. Reasoning
| Aspect | Value |
|---|---|
| Input | `graph: CandidateGraph`, `role: RoleDNA` |
| Output | `CandidateReasoning` |
| Shared interface | `ReasoningEngine.reason(...)` (async) |
| Concrete impl | Developer 4 `app.intelligence.reasoning.reasoning_engine.ReasoningEngine` (sync) |
| Adapter | `ReasoningEngineAdapter` |
| DI provider | `deps.get_reasoning_engine()` |
| Notes | Graph-present → native engine. Graph-disabled → claims synthesized from `metadata.evidence`, then Dev 4's own gap/uncertainty/confidence/summary engines (`metadata.reasoning_mode="evidence_fallback"`). |

### 6. Decision
| Aspect | Value |
|---|---|
| Input | `reasoning: CandidateReasoning`, `role: RoleDNA` |
| Output | `HiringDecision` |
| Shared interface | `DecisionEngine.decide(...)` (async) |
| Concrete impl | Developer 4 `app.intelligence.decision.decision_engine.DecisionEngine` (sync) |
| Adapter | `DecisionEngineAdapter` |
| DI provider | `deps.get_decision_engine()` |
| Notes | Rebuilds native `ReasoningResult` from `CandidateReasoning` (metadata counts), calls untouched `decide()`, maps `Recommendation`→`RecommendationLevel`. |

### 7. Ranking (two-stage)
| Aspect | Value |
|---|---|
| Input | RETRIEVAL: `job_id, RoleDNA, candidates: list[dict], top_k` · RERANK: `job_id, decisions: list[HiringDecision], limit` |
| Output | RETRIEVAL: `list[CandidateRanking]` · RERANK: `RankedList` |
| Shared interface | `RankingEngine.retrieve(...)` / `.rerank(...)` (async) |
| Concrete impl | `app.runtime.deterministic_ranking_engine.DeterministicRankingEngine` |
| Adapter | none — native conforms |
| DI provider | `deps.get_ranking_engine()` (DeterministicRankingEngine = **default impl only**) |
| Notes | Runtime never names the concrete class; future engines swap behind the interface. |

### 8. Explainability
| Aspect | Value |
|---|---|
| Input | (embedded) `HiringDecision` fields |
| Output | `HiringDecision.{reasons, reservations, interview_focus, recommendations, summary}` |
| Shared interface | none — explainability is a property of the decision contract |
| Concrete impl | produced by `DecisionEngineAdapter` from Dev 4's rationale/blockers + reasoning gaps |
| Adapter | (within `DecisionEngineAdapter`) |
| DI provider | n/a (carried on the decision) |
| Notes | No separate v2 explainability engine; the recruiter-facing rationale rides on `HiringDecision`. World A's `explainability_engine` is untouched and unused by v2. |

---

## Composed runtime objects

| Object | Role | Spans stages | Constructed by |
|---|---|---|---|
| `PipelineContext` (`app.shared.context`) | mutable per-(candidate,job) carrier; holds evidence/graph/reasoning/decision + `telemetry` | all | the pipeline |
| `Stage` adapters (`app.runtime.stages`) | read ctx → call interface → write ctx (no conversion) | 2–6 | `CandidateEvaluationPipeline` |
| `PipelineRuntime` (`app.runtime.pipeline_runtime`) | ordered async executor; records per-stage `{status,duration_ms}` + `total_ms`; `fail_fast` | 2–6 | `CandidateEvaluationPipeline` |
| `CandidateEvaluationPipeline` | per-candidate chain Evidence→Graph→Fusion→Reasoning→Decision → `HiringDecision` | 2–6 | `deps.get_candidate_evaluation_pipeline()` |
| `RankingOrchestrator` | batch: evaluate each candidate, then rerank → `RankedList` | 2–7 | `deps.get_ranking_orchestrator()` |

---

## Telemetry contract

- **Per stage:** `ctx.telemetry["stages"][<name>] = {"status": ok\|error\|cancelled, "duration_ms": float[, "error": str]}` (recorded by `PipelineRuntime`).
- **Run total:** `ctx.telemetry["total_ms"]`.
- **Graph skip:** `graph.metadata = {graph_disabled, graph_stage:"skipped", adapter, reason, evidence_count, evidence}`.
- **Fusion skip:** `graph.metadata.fusion_stage = "skipped"`.
- **Reasoning mode:** `reasoning.metadata.reasoning_mode = "evidence_fallback"` when graph disabled.
- **Warnings:** `ctx.warnings` (graceful, non-fatal stage notes when `fail_fast=False`).

---

## Failure semantics (graceful)

| Failure | Behaviour |
|---|---|
| One evidence source bad/empty/raises | that provider yields `[]`; other sources unaffected; pipeline continues |
| Reasoning/decision raises for one candidate | candidate dropped by `RankingOrchestrator` (logged); batch continues |
| Graph/Fusion | cannot fail meaningfully (no-ops) |
| Whole-pipeline | `evaluate()` raises `PipelineError` only if no decision is produced; orchestrator isolates it per candidate |

The contract: a single bad source or candidate never collapses the batch, and every stage
records telemetry whether it succeeds or degrades.
