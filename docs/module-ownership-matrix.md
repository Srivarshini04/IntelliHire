# DELULU Backend — Module Ownership & Dependency Matrix (Phase 1.5)

**Branch:** `develop` @ `721784c`
**Purpose:** Authoritative integration checklist. One row per logical module.
**Scope reminder:** World A (`/api/*`) is the existing production backend and is
**OFF-LIMITS** — no modification, no internal rerouting, no frontend migration. The
integration objective is to make **World B (`/v2/*`)** complete and operational using only
completed modules (Developers 1, 2, 4), with `NoOpGraphAdapter` standing in for the absent
Developer 3 graph work.

---

## Legend

**Owner** (per directive capability mapping; corroborated by git authorship)
- **D1** — Developer 1: Shared Contracts, Runtime, Role DNA, Pipeline Orchestration, Deterministic Ranking Engine, v2 Foundation (git: *venuenugula*)
- **D2** — Developer 2: Resume / GitHub / LinkedIn / LeetCode Intelligence, Evidence Providers (git: *Srivarshini04*, *Anusha*, venuenugula)
- **D3** — Developer 3: Graph Intelligence (**NOT completed**)
- **D4** — Developer 4: Candidate Reasoning, Decision Engine, Explainability, Interview Recommendation, Risk Engine (git: *Anjali*)
- **Shared/Infra** — cross-cutting foundation (owned by D1 in practice)

**Status:** `Complete` · `Partial` · `Stub` · `Missing`
**World:** `B` = v2 integration target · `A` = existing /api backend (do not modify)
**Integration Required:** does *this* integration phase need to touch/wire it?

---

## A. Developer 1 — Shared Contracts, Runtime, Role DNA, v2 Foundation (World B)

| Module | Owner | Status | Uses shared? | Runtime integration today | Depends on | Used by | Integration req? | Notes |
|---|---|---|---|---|---|---|---|---|
| `app/shared/interfaces/pipeline.py` | D1 | Complete | n/a (defines) | Source of truth for engine Protocols | shared.models/enums/constants | role_dna route, ranking route, runtime, stages | **No** (do not edit) | Frozen contracts. All engines must conform via adapters. |
| `app/shared/models/*` | D1 | Complete | n/a (defines) | Canonical domain models | shared.enums | nearly all v2 modules | **No** (do not edit) | Single source of truth (Rule 2). |
| `app/shared/enums/`, `app/shared/constants/` | D1 | Complete | n/a | Canonical enums/constants | — | shared.models, engines, ranking | **No** | — |
| `app/shared/context/pipeline_context.py` | D1 | Complete | Yes | Per-candidate runtime context | shared.models | runtime stages, pipeline | **No** | Distinct from `intelligence/pipeline_context.py` (name clash only). |
| `app/runtime/pipeline_runtime.py` | D1 | Complete | Yes | Generic stage executor (timing/telemetry/errors) | runtime.stage, shared.context | candidate_evaluation_pipeline | **No** (reuse) | Already emits per-stage telemetry. |
| `app/runtime/stage.py`, `app/runtime/stages.py` | D1 | Complete | Yes | Stage base + Evidence/Graph/Fusion/Reasoning/Decision adapters | shared.interfaces, shared.context | candidate_evaluation_pipeline | **Maybe** | Stages call injected interfaces. `GraphStage` will receive `NoOpGraphAdapter`. |
| `app/runtime/candidate_evaluation_pipeline.py` | D1 | Complete | Yes | Per-candidate chain Evidence→Graph→Fusion→Reasoning→Decision | runtime.pipeline_runtime, stages, shared.* | ranking_orchestrator | **Yes (wire)** | Built but **not constructed anywhere** — needs DI assembly (Phase 3). |
| `app/runtime/ranking_orchestrator.py` | D1 | Complete | Yes | Batch evaluate + rerank | candidate_evaluation_pipeline, shared.interfaces RankingEngine | (none yet) | **Yes (wire)** | Not constructed anywhere — DI assembly (Phase 3). |
| `app/runtime/deterministic_ranking_engine.py` | D1 | Complete | Yes | RankingEngine impl | shared.models/constants | runtime.deps | **No** (default DI only) | Register behind `RankingEngine` interface, never reference concretely in runtime. |
| `app/runtime/deps.py` | D1 | Partial | Yes | DI providers: RoleDNA + ranking | role_dna provider, deterministic engine, shared.interfaces | role_dna route, ranking route | **Yes (extend)** | Add providers for evidence list, reasoning, decision, NoOpGraph, pipeline, orchestrator (Phase 3). |
| `app/intelligence/role_dna/role_dna_provider.py` | D1 | Complete | Yes | `BlueprintRoleDNAProvider` (conforms to Protocol) | shared.models, knowledge | role_dna route (via deps) | **No** | Already wired & working. |
| `app/intelligence/role_dna/inference.py` | D1 | Complete | Yes | RoleDNA enrichment helpers | knowledge | role_dna_provider | **No** | — |
| `app/api/v2/router.py`, `app/api/v2/schemas.py` | D1 | Complete | Yes | Mounts the 6 v2 routers | route modules, shared.models | main.py | **No** | OpenAPI builds. |

---

## B. Developer 1 — v2 API routes (World B) — *current wiring status*

| Route module | Owner | Status | Runtime integration today | Integration req? | Notes |
|---|---|---|---|---|---|
| `app/api/v2/routes/role_dna.py` | D1 | **Complete** | Wired → `get_role_dna_provider` (DI) | **No** | `POST /v2/role-dna/generate` is real. |
| `app/api/v2/routes/ranking.py` | D1 | **Complete** | Wired → `get_deterministic_ranking_engine` (DI) | **Minor** | `POST /v2/ranking/rank` is real; rename provider to interface-typed `get_ranking_engine` so the route depends on `RankingEngine`, not the concrete name. |
| `app/api/v2/routes/evidence.py` | D1 | **Stub** | None (returns `[]`) | **Yes** | Wire to evidence provider adapters (Phase 5). |
| `app/api/v2/routes/reasoning.py` | D1 | **Stub** | None | **Yes** | Wire to ReasoningEngine adapter. |
| `app/api/v2/routes/decision.py` | D1 | **Stub** | None | **Yes** | Wire to DecisionEngine adapter. |
| `app/api/v2/routes/graph.py` | D3-area | **Stub** | None | **Decide** | Keep as no-op/telemetry endpoint backed by `NoOpGraphAdapter`; do **not** build graph logic. |

> **Correction to Phase 1 audit:** `role_dna` and `ranking` routes are already wired (not stubs). Only `evidence`, `reasoning`, `decision`, `graph` are stubs.

---

## C. Developer 2 — Evidence Providers & Source Intelligence

| Module | Owner | Status | Uses shared? | Runtime integration today | Depends on | Used by | Integration req? | Notes |
|---|---|---|---|---|---|---|---|---|
| `app/services/evidence/base.py` (`EvidenceProvider`, `EvidenceObject`) | D2 | Complete | **No** (own `EvidenceObject`, `source: str`) | World A only | pipeline.evidence_sources | schemas.candidate, normalizer | **Yes (adapt)** | Protocol mismatch vs `shared.interfaces.EvidenceProvider` → needs adapter to emit `shared.models.Evidence` (Phase 2/3). |
| `app/services/evidence/github_service.py` (+ extractor/parser) | D2 | Complete | No | World A (`/api/github`, analysis_pipeline) | base, pipeline.* | analysis_pipeline, github route | **Yes (adapt)** | Wrap for v2 evidence stage. |
| `app/services/evidence/linkedin_service.py` (+ extractor/parser) | D2 | Complete | No | World A (`/api/linkedin`) | base | analysis_pipeline, linkedin route | **Yes (adapt)** | — |
| `app/services/evidence/leetcode_service.py` (+ engine) | D2 | Complete | No | World A (`/api/leetcode`) | base | analysis_pipeline, leetcode route | **Yes (adapt)** | — |
| `app/services/evidence/portfolio_service.py` (+ extractor) | D2 | Complete | No | World A (`/api/portfolio`) | base | analysis_pipeline, portfolio route | **Yes (adapt)** | — |
| `app/services/evidence/resume_parser.py`, `skill_extractor.py`, `relevance_engine.py`, `normalizer.py` | D2 | Complete | Partial | World A | base, skills | analysis_pipeline | **Maybe** | `normalizer.py` is the "Evidence Normalization" candidate for the v2 chain. |
| `app/intelligence/resume/*` (profile extractor/orchestrator/validator, url/identity resolver) | D2 | Complete | Partial | World A (resume intelligence) | documents, llm, knowledge | analysis_pipeline | **No** (World A) | Feeds resume evidence; reachable for v2 via adapter if needed. |
| `app/documents/*` (service, chunker, pii, quality, artifacts, storage) | D2 | Complete | Partial | World A document understanding | schemas.document | resume intelligence | **No** (World A) | — |
| `app/github_intel/*` | D2 | Complete | No | World A (separate SQLite DB) | own Base | github route/seed | **No** (World A) | Independent DB; leave as-is. |
| `app/pipeline/*` (GitHub deep extractor lineage) | D2 | Complete | No | World A | many internal | github_service, analysis_pipeline | **No** (World A) | Legacy lineage; §3b duplicate schemas (tech debt). |

---

## D. Developer 3 — Graph Intelligence (NOT completed)

| Module | Owner | Status | Uses shared? | Runtime integration today | Integration req? | Notes |
|---|---|---|---|---|---|---|
| `GraphBuilder` (class implementing `shared.interfaces.GraphBuilder`) | D3 | **Missing** | — | — | **No (do not build)** | Replace with `NoOpGraphAdapter`. |
| `FusionEngine` (class implementing `shared.interfaces.FusionEngine`) | D3 | **Missing** | — | — | **No (do not build)** | No real fusion; covered by no-op passthrough. |
| `app/intelligence/candidate_graph/graph_schema.py` | D3 | Stub (shim) | Yes (re-export) | — | **No** | Deprecated shim → `shared.models`. Keep. |
| `app/intelligence/candidate_graph/confidence_fusion.py` | D3 | Partial (1 fn) | Yes (constants) | Not wired | **No** | Helper only; not a `FusionEngine`. Do not wire. |
| `app/intelligence/candidate_graph/entity_resolver.py` | D3 | Partial (helpers) | Yes (knowledge) | Not wired | **No** | Helper only; not used in runtime. |
| `app/models/graph.py`, `app/models/ledger.py` | D3-area | Stub/ORM | — | Not used | **No** | Scaffolding for future graph persistence. |
| `app/repositories/graph.py`, `app/repositories/ledger.py` | D3-area | Stub/ORM | — | Not used | **No** | Scaffolding. |
| **`NoOpGraphAdapter`** (to create) | D1/integration | **To build** | Yes | Will satisfy `GraphBuilder` interface | **YES (Phase 3)** | Passes evidence through unchanged + emits "graph stage skipped" telemetry. Nothing more. |

---

## E. Developer 4 — Reasoning, Decision, Explainability, Risk

| Module | Owner | Status | Uses shared? | Runtime integration today | Depends on | Used by | Integration req? | Notes |
|---|---|---|---|---|---|---|---|---|
| `app/intelligence/reasoning/reasoning_engine.py` | D4 | Complete | Partial | **Not wired** (sync, returns `ReasoningResult`) | reasoning.* submodules, shared.models | decision_engine | **Yes (adapt)** | Adapter: sync→async, `ReasoningResult`→`CandidateReasoning`; bridge evidence-through-NoOpGraph input. |
| `app/intelligence/reasoning/{claim_synthesizer,gap_analyzer,uncertainty_detector,confidence_engine,summary_composer,materiality_resolver,types}.py` | D4 | Complete | Partial | Internal to reasoning | shared.models | reasoning_engine | **No** | Engine internals; don't touch. |
| `app/intelligence/decision/decision_engine.py` | D4 | Complete | Partial | **Not wired** (sync, returns `DecisionResult`) | reasoning outputs, shared.models | (none yet) | **Yes (adapt)** | Adapter: sync→async, add `role`, `DecisionResult`→`HiringDecision`, map `Recommendation`→`RecommendationLevel`. |
| `app/services/risk/risk_engine.py` | D4 | Complete | No | World A (analysis_pipeline) | evidence data | analysis_pipeline | **No** (World A) | Risk Engine; v1 scoring stack. |
| `app/services/ranking/explainability_engine.py` | D4 | Complete | No | World A (analysis_pipeline) | — | analysis_pipeline | **Decide** | "Explainability" stage in required pipeline. For v2, decision `summary`/`reasons` already provide explainability; wiring this World-A engine is optional and must not modify World A. |
| `app/services/ranking/ranking_engine.py` (`compute_fit_score`) | D4/D2 | Complete | No | World A | — | analysis_pipeline | **No** (World A) | v1 fit score; not the v2 `RankingEngine`. |
| `app/services/summary/summary_engine.py` | D2/D4 | Complete | No | World A (`/api`) | — | candidates summary | **No** (World A) | — |

---

## F. Shared infrastructure / cross-cutting (D1 / Shared)

| Module | Owner | Status | Uses shared? | Runtime integration | Integration req? | Notes |
|---|---|---|---|---|---|---|
| `app/core/{config,database,security}.py` | D1 | Complete | n/a | App bootstrap (both worlds) | **No** | Shared config/DB/auth. |
| `app/llm/{base,factory,gemini}.py` | D1 | Complete | n/a | Used by JD/resume/reasoning where LLM needed | **No** | `google.generativeai` deprecation warning (non-blocking). |
| `app/knowledge/{loader,normalizer}.py` | D1 | Complete | Yes | Role DNA, entity_resolver, skills | **No** | Shared knowledge layer. |
| `app/skills/{matching,normalizer}.py` | D1/D2 | Complete | Partial | World A scoring + knowledge | **No** | — |
| `app/intelligence/jd/*` (blueprint pipeline, approval, validators, telemetry) | D1 | Complete | Partial | World A (`/api/jobs/blueprint`, `/approve`) + feeds Role DNA | **No** (World A) | "Role Blueprint" upstream of Role DNA; reachable by v2 via the blueprint dict already accepted by RoleDNA route. |
| `app/intelligence/pipeline_context.py` | D1 | Complete | No | JD/document orchestration context | **No** | Name clash with v2 runtime context (cosmetic). |
| `app/intelligence/{base_orchestrator,stage_registry,prompt_registry,telemetry,validation,feedback}.py` | D1 | Complete | Partial | JD/resume orchestration | **No** | World A orchestration scaffolding. |
| `app/mock/*` | D1 | Complete | Yes | Contract conformance fixtures | **No** | Useful for integration tests (Phase 7). |

---

## G. World A — existing /api production backend (DO NOT MODIFY)

| Area | Owner | Status | Notes |
|---|---|---|---|
| `app/api/{jobs,candidates,github,linkedin,leetcode,portfolio,analysis,resume,documents,rankings}.py` | D1/D2 | Complete | Frontend (`frontend/src/lib/api.ts`) consumes these. **Untouched** (Rule 4). |
| `app/services/analysis_pipeline.py` | D1/D2/D4 | Complete | World A orchestrator. Reference only; do not reroute. |
| `app/services/{capability,confidence,hti}/*` | D2 | Complete | v1 scoring stack. World A. |
| `app/models/*` (ORM), `app/schemas/*` (Pydantic I/O) | D1 | Complete | Persistence + API I/O for World A. Distinct from `app/shared/models`. |
| `app/repositories/{decision,reasoning,ranking}.py`, `_util.py` | D1 | Complete/Stub | v2-side persistence scaffolding; not required for the in-memory v2 runtime path. |

---

## H. Integration checklist (the actionable subset — World B only)

Ordered by phase. Everything here is **adapters / DI / wiring** — no rewrites, no World A edits.

| # | Action | New/Touched file(s) | Phase |
|---|---|---|---|
| 1 | Adapter: Dev 2 evidence services → `shared.interfaces.EvidenceProvider` (emit `shared.models.Evidence`, `EvidenceSource`) | new `app/runtime/adapters/evidence_adapter.py` (or `app/intelligence/...`) | 2/3 |
| 2 | `NoOpGraphAdapter` implementing `GraphBuilder` (passthrough + telemetry) | new `app/runtime/adapters/noop_graph_adapter.py` | 3 |
| 3 | Adapter: Dev 4 `ReasoningEngine` (sync→async, `ReasoningResult`→`CandidateReasoning`) | new `app/runtime/adapters/reasoning_adapter.py` | 3 |
| 4 | Adapter: Dev 4 `DecisionEngine` (sync→async, add role, `DecisionResult`→`HiringDecision`, enum map) | new `app/runtime/adapters/decision_adapter.py` | 3 |
| 5 | Fusion: no-op passthrough conforming to `FusionEngine` (graph empty/skipped) | within NoOpGraph adapters or `app/runtime/adapters/` | 3 |
| 6 | Extend DI: providers for evidence list, NoOpGraph, fusion, reasoning, decision, `CandidateEvaluationPipeline`, `RankingOrchestrator`; interface-typed `get_ranking_engine` | `app/runtime/deps.py` | 3 |
| 7 | Wire `/v2/evidence/extract` → evidence adapter(s) | `app/api/v2/routes/evidence.py` | 5 |
| 8 | Wire `/v2/reasoning/run` → reasoning adapter | `app/api/v2/routes/reasoning.py` | 5 |
| 9 | Wire `/v2/decision/generate` → decision adapter | `app/api/v2/routes/decision.py` | 5 |
| 10 | `/v2/graph/build` → back with `NoOpGraphAdapter` (telemetry; no graph logic) | `app/api/v2/routes/graph.py` | 5 |
| 11 | Decouple ranking route from concrete engine name (interface-typed DI) | `app/api/v2/routes/ranking.py`, `deps.py` | 3/5 |
| 12 | Integration tests: missing resume/GitHub/LinkedIn, empty evidence, provider failure, graph disabled | new `tests/test_v2_integration*.py` | 7 |

**Not in scope / explicitly excluded:** Candidate Graph, Graph Builder, Confidence Fusion,
Entity Resolution, Evidence Ledger, Graph APIs (D3); any World A (`/api/*`) change; frontend.

---

## I. Summary counts

- v2 routes: **2 complete** (role-dna, ranking), **4 to wire** (evidence, reasoning, decision, graph).
- Engines needing adapters: **3** (evidence providers, reasoning, decision) + **1 no-op** (graph) + **1 no-op** (fusion).
- DI to extend: **1** file (`runtime/deps.py`).
- World A modules to modify: **0** (by rule).
- D3 modules to implement: **0** (only `NoOpGraphAdapter`).
