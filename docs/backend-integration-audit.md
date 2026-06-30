# DELULU Backend Integration — Phase 1 Repository Audit

**Branch audited:** `develop` @ `721784c` (latest, fast-forwarded from origin)
**Scope:** Read-only audit. No application code modified in this phase.
**Role:** Principal Backend Integration Engineer

---

## 0. Executive summary

The backend is **healthy at the unit level** — all 211 modules import cleanly, there
are **no broken imports**, **no circular-import failures**, the FastAPI app builds, and
**293/293 tests pass**. OpenAPI builds with **24 paths**.

The repository contains **two parallel generations** of the backend. The integration
target (the DELULU **v2** pipeline) is currently **un-wired — every `/v2/*` route is a
stub**. There are **contract mismatches** between the frozen v2 Protocols and the real
engines (reconcilable with adapters, per Rule 1), and **Graph Intelligence (Developer 3)
is confirmed absent** (→ `NoOpGraphAdapter`, per Rule 3).

---

## 1. Import health

| Check | Result |
|---|---|
| Modules discovered under `app.` | 211 |
| Import failures | **0** |
| Circular-import failures (at import time) | **0** |
| `app.main` imports + app builds | ✅ |
| OpenAPI schema builds | ✅ (24 paths) |
| Test suite | **293 passed**, 0 failed (2 deprecation warnings) |

Warnings are non-blocking (`google.generativeai` deprecation; Python 3.10 EOL notice).

> Interpreter note: the working venv is the **repo-root `.venv`** (`backend/.venv` lacks
> deps). All checks above were run with `../.venv/bin/python` from `backend/`.

---

## 2. The two-generations structure

### World A — "v1", currently powering the frontend (leave untouched, per Rule 4)
- Orchestrator: `app/services/analysis_pipeline.py` (`analyze_candidate`)
- Evidence: `app/services/evidence/*` (GitHub, LinkedIn, LeetCode, Portfolio, Resume)
- Scoring: `app/services/{capability,confidence,hti,risk,ranking,summary}/*`
- Models: `app/models/*` (SQLAlchemy ORM) + `app/schemas/*` (Pydantic I/O)
- APIs: `/api/*`. The frontend (`frontend/src/lib/api.ts`) calls
  `http://localhost:8000/api` **only**. This is the backend the frontend uses today and
  it already runs end-to-end.

### World B — "v2 DELULU", the integration target
- Contracts: `app/shared/*` (interfaces, models, enums, constants, context)
- Runtime: `app/runtime/*` (`PipelineRuntime`, `CandidateEvaluationPipeline`,
  `RankingOrchestrator`, `DeterministicRankingEngine`, stages, `deps.py`)
- Engines: `app/intelligence/{role_dna,reasoning,decision}`
- APIs: `/v2/*` — **all stubs** (`metadata.stub = True`, no real engine wired).

Required pipeline (per directive) maps onto World B:
`JD → Role Blueprint → Role DNA → Evidence Providers → Evidence Normalization →
NoOpGraphAdapter → Reasoning → Decision → Deterministic Ranking → Explainability → API`.

---

## 3. Duplicate definitions

18 class names appear in more than one place. Categorized:

### 3a. Legitimate (not contract violations)
| Name | Locations | Verdict |
|---|---|---|
| `Base` | `core/database.py`, `github_intel/database.py` | Two SQLAlchemy bases / two DBs — intentional. |
| `CandidateGraph`, `Evidence`, `CandidateRanking`, `CandidateReasoning`, `HiringDecision`, `EvidenceLedgerEntry` | `app/models/*` **and** `app/shared/models/*` | `app/models/*` = ORM rows (persistence); `app/shared/models/*` = domain contracts (Pydantic). Different layers. Name overlap is a footgun but not a redefinition of a contract. |
| `DecisionEngine`, `ReasoningEngine`, `EvidenceProvider` | `app/shared/interfaces/pipeline.py` (Protocol) **and** impl modules | Interface vs implementation — but impls don't currently satisfy the Protocols (see §4). |

### 3b. Name collisions inside World A (pre-existing tech debt, off the v2 path)
`AnalyzeResponse`, `ArchitectureFeatures`, `CandidateProfile`, `GitHistoryMetrics`,
`HiddenGemResult`, `VerifiedSkill`, `LinkedInAnalyzeRequest` — within `app/pipeline/*` +
`app/schemas/*`. Out of scope for this integration; flagged only.

### 3c. `PipelineContext` — one name, two unrelated objects
- `app/shared/context/pipeline_context.py` — v2 candidate-evaluation context (runtime).
- `app/intelligence/pipeline_context.py` — JD/document-processing context (JD orchestrator).

Not a duplicated contract. No correctness action; rename candidate later.

### Duplicate enums / repositories
**0 duplicate enums.** Repositories (`app/repositories/*`) are single-definition. ✅

---

## 4. Contract mismatches (resolve via adapters — Rule 1, Rule 2)

The frozen v2 Protocols in `app/shared/interfaces/pipeline.py` do **not** match the real
engines. Per Rule 1 these are wrapped with adapters (no rewrites); per Rule 2 the
canonical models stay in `app/shared`.

| Protocol (shared, **async**) | Real implementation | Mismatch to bridge |
|---|---|---|
| `EvidenceProvider.collect(candidate_id, raw: dict) -> list[Evidence]`, `source: EvidenceSource` | `app/services/evidence/base.py`: `collect(identifier, role_blueprint, **kwargs) -> EvidenceObject`, `source: str`; providers also expose `analyze_*_evidence()` functions | model `EvidenceObject` → `shared.models.Evidence`; signature; `str` → `EvidenceSource` |
| `ReasoningEngine.reason(graph, role) -> CandidateReasoning` | `app/intelligence/reasoning/reasoning_engine.py`: **sync** `reason(graph, role) -> ReasoningResult` | sync→async; `ReasoningResult` → `CandidateReasoning` |
| `DecisionEngine.decide(reasoning, role) -> HiringDecision` | `app/intelligence/decision/decision_engine.py`: **sync** `decide(result) -> DecisionResult`; own `Recommendation` enum | sync→async; add `role`; `DecisionResult` → `HiringDecision`; `Recommendation` → `RecommendationLevel` |

**Note on `reason(graph, role)`:** the impl requires a `CandidateGraph`. Per Rule 3 the
`NoOpGraphAdapter` "passes evidence forward." Bridging this so reasoning receives evidence
through the no-op graph is the key adapter to design in Phase 3/4 (the adapter assembles a
**passthrough** carrier of the existing evidence — no entity resolution, no fusion, no
inference — and emits "graph skipped" telemetry).

---

## 5. Graph Intelligence (Developer 3) — confirmed absent (→ NoOpGraphAdapter)

Under `app/intelligence/candidate_graph/`:
- `graph_schema.py` — deprecated shim re-exporting from `app.shared.models` (no logic).
- `confidence_fusion.py` — one pure function `fuse_confidence(list) -> float`.
- `entity_resolver.py` — `resolve_skill` / `resolve_organization` helpers.

There is **no `GraphBuilder` and no `FusionEngine` class** implementing the v2 Protocols.
`app/models/graph.py`, `app/models/ledger.py`, `app/repositories/{graph,ledger}.py`,
`app/api/v2/routes/graph.py` are ORM/stub scaffolding. ⇒ **`NoOpGraphAdapter` (Rule 3) is
the correct and only graph wiring.** Do not implement Candidate Graph / Entity Resolution
/ Confidence Fusion / Graph APIs / Evidence Ledger.

---

## 6. API & runtime conflicts

- **No route path collisions.** All 24 OpenAPI paths unique; `/api/*` and `/v2/*` cleanly
  namespaced; health at `/health`.
- **No runtime conflicts.** Worlds A and B share `app/shared` constants/models without
  contention; two SQLAlchemy bases target separate DBs.
- **Stub routes:** `/v2/{role-dna,evidence,graph,reasoning,decision,ranking}` return
  `stub: True` placeholders (schema-correct, compute nothing). Phase 5 removes the stubs.
- **DI today (`app/runtime/deps.py`):** provides only `RoleDNAProvider`
  (`BlueprintRoleDNAProvider`) and a `RankingEngine` (`DeterministicRankingEngine`). The
  evidence/reasoning/decision engines, `CandidateEvaluationPipeline`, and
  `RankingOrchestrator` are **not** yet provided via DI (Phase 3).

---

## 7. Decisions — resolved by the integration directive

| # | Question raised by audit | Resolution (per directive) |
|---|---|---|
| 1 | Ranking engine (no `ChallengeRankingEngine` exists) | Use **`DeterministicRankingEngine`** (Developer 1). `ChallengeRankingEngine` is not in scope. |
| 2 | Reasoning without a graph | **`NoOpGraphAdapter` passes evidence forward** + emits "graph skipped" telemetry. No empty/fake graph (Rule 3). |
| 3 | "Powers the frontend" vs wire v2 | **Make `/v2/*` real; leave the frontend on `/api/*`** (Rule 4). Optionally wire `/api` internally to the runtime without breaking compatibility. |
| 4 | Bridging Protocol↔impl mismatches | **Adapters/wrappers/DI only** — never rewrite another developer's module (Rule 1). |

---

## 8. Tech debt & dead-code candidates (informational; not actioned this phase)

- `app/api/v2/routes/graph.py` + graph ORM/repos — scaffolding for an unbuilt module.
- World A `app/pipeline/*` legacy GitHub-extractor lineage with near-duplicate schemas (§3b).
- `app/intelligence/pipeline_context.py` name collision with the v2 runtime context (§3c).
- `backend/.venv` lacks dependencies; the functional interpreter is the repo-root `.venv`.

---

## 9. Phase 1 verdict

**PASS.** The repo is structurally sound and fully importable/testable; no emergency fixes
required. The contract mismatches (§4) and absent graph (§5) are expected and handled by
adapters + `NoOpGraphAdapter` in later phases. All directive decisions (§7) are resolved.
**No application code was modified in this phase.**
