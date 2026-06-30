# DELULU Backend Readiness Report

**Status:** Final engineering report for the DELULU v2 backend integration.
**Branch:** `develop` @ `721784c` (+ uncommitted integration work).
**Audience:** Backend, frontend, and platform engineers; the future Graph Intelligence author.
**Companion docs:** [audit](backend-integration-audit.md) · [ownership matrix](module-ownership-matrix.md) ·
[contract verification](contract-verification.md) · [adapter conversion](adapter-conversion-report.md) ·
[runtime execution contract](runtime-execution-contract.md) · [e2e verification](phase6-verification-report.md) ·
[production readiness audit](production-readiness-audit.md).

---

## 1. Overview

DELULU evaluates candidates against jobs and ranks them. This report describes the **v2
backend** delivered by the integration effort: a clean, Protocol-driven hiring pipeline
(RoleDNA → Evidence → Graph → Reasoning → Decision → Ranking) exposed to the frontend
through a resource-oriented business API, and fully operational **without** the
not-yet-built Graph Intelligence module.

The integration added **only wiring and adapters** — no developer's engine was rewritten,
no shared contract was redefined, and the existing World A `/api` backend was left
untouched.

> **Key limitation (stated explicitly, not hidden):** Candidate Graph, Entity Resolution,
> Confidence Fusion, and Evidence Ledger are **not yet integrated**. The runtime currently
> uses **`NoOpGraphAdapter`**. Reasoning therefore runs in an evidence-based fallback mode
> until Graph Intelligence lands; replacing `NoOpGraphAdapter` with the real
> `CandidateGraphAdapter` in dependency injection requires **zero** runtime or API changes.

---

## 2. Architecture

### 2.1 Two coexisting generations
- **World A (`/api/*`)** — the existing production backend that currently powers the
  frontend (`app/services/analysis_pipeline.py`, `app/models`, `app/schemas`). **Untouched**
  by this integration.
- **World B (`/v2/*`)** — the DELULU v2 runtime this report covers (`app/shared`,
  `app/runtime`, `app/intelligence`, `app/api/v2`).

### 2.2 Layered design (v2)
```
Frontend (business entities only)
        │   POST /v2/evaluations · POST /v2/rankings
        ▼
API layer            app/api/v2/routes/*            (thin; no conversion)
        ▼
Application service   app/api/v2/evaluation_service  (orchestrates + shapes business DTOs)
        ▼
Composition root      app/runtime/deps              (DI; binds interfaces → implementations)
        ▼
Runtime              app/runtime/pipeline_runtime, stages, candidate_evaluation_pipeline,
                     ranking_orchestrator           (ordered async stages + telemetry)
        ▼
Anti-corruption      app/runtime/adapters/*         (the ONLY contract-translation boundary)
        ▼
Engines              Dev2 evidence · Dev4 reasoning/decision · Dev1 RoleDNA/ranking
        ▲
Contracts (SSOT)     app/shared (models, enums, interfaces, context, constants)
```

### 2.3 Principles enforced
- **`app/shared` is the single source of truth** — no contract redefined.
- **Anti-corruption layer** — every model conversion lives in `app/runtime/adapters/`;
  routes, stages, and DI never convert.
- **Dependency injection** — engines are bound behind their shared interface in
  `app/runtime/deps`; nothing names a concrete implementation outside DI (ranking depends
  on `RankingEngine`; `DeterministicRankingEngine` is the default impl only).
- **Pipeline encapsulation** — the frontend speaks business entities; pipeline objects
  (CandidateGraph, RoleDNA, Evidence, CandidateReasoning) never cross the API boundary.
- **Graceful degradation** — missing/failed sources and the absent graph degrade, never crash.

---

## 3. Implemented modules

### 3.1 Developer 1 — contracts, runtime, RoleDNA, ranking (complete)
`app/shared/*` (models, enums, interfaces, context, constants); `app/runtime/*`
(`PipelineRuntime`, `CandidateEvaluationPipeline`, `RankingOrchestrator`,
`DeterministicRankingEngine`, stages, `deps`); `app/intelligence/role_dna/*`
(`BlueprintRoleDNAProvider`). v2 API scaffolding `app/api/v2/*`.

### 3.2 Developer 2 — evidence & source intelligence (complete)
`app/services/evidence/*` (GitHub, LinkedIn, LeetCode, Portfolio, Resume) + `normalizer`
(`normalize() → EvidenceObject`). Reused via adapter; not modified.

### 3.3 Developer 4 — reasoning & decision (complete)
`app/intelligence/reasoning/*` (claim synthesis, gap, uncertainty, confidence, summary)
and `app/intelligence/decision/decision_engine`. Reused via adapter; not modified.

### 3.4 Integration layer (added by this effort)
| Component | File | Role |
|---|---|---|
| `EvidenceProviderAdapter` | `runtime/adapters/evidence_adapter.py` | `EvidenceObject` → `list[Evidence]`; per-source failure isolation |
| `NoOpGraphAdapter` | `runtime/adapters/noop_graph_adapter.py` | graph passthrough + telemetry; carries evidence for fallback |
| `NoOpFusionEngine` | `runtime/adapters/noop_graph_adapter.py` | graph-disabled fusion no-op |
| `ReasoningEngineAdapter` | `runtime/adapters/reasoning_adapter.py` | Dev4 sync → async; evidence-fallback reasoning when graph disabled |
| `DecisionEngineAdapter` | `runtime/adapters/decision_adapter.py` | Dev4 sync → async; `DecisionResult` → `HiringDecision` |
| DI composition root | `runtime/deps.py` | binds every engine + assembles pipeline/orchestrator |
| `EvaluationService` | `api/v2/evaluation_service.py` | drives runtime; shapes business DTOs |
| Business API | `api/v2/routes/evaluations.py` | `POST /v2/evaluations`, `POST /v2/rankings` |

### 3.5 Runtime stage contract
See [runtime-execution-contract.md](runtime-execution-contract.md) for the per-stage
input/output/interface/impl/adapter/DI table and telemetry contract.

---

## 4. Deferred modules (not implemented — intentional)

| Module (Developer 3) | State | Runtime handling |
|---|---|---|
| Candidate Graph (`GraphBuilder`) | Not implemented | `NoOpGraphAdapter` (passthrough + telemetry) |
| Confidence Fusion (`FusionEngine`) | Not implemented | `NoOpFusionEngine` (no-op) |
| Entity Resolution | Not implemented | Minimal slug ids in the evidence adapter; refs aligned to RoleDNA in the reasoning adapter |
| Evidence Ledger | Not implemented | Evidence carried on `graph.metadata.evidence` for the fallback |
| Graph APIs | Not implemented | `/v2/graph/build` backed by `NoOpGraphAdapter` (internal/debug) |

**Replacement path:** implement `CandidateGraphAdapter` (and a real `FusionEngine`),
register them in `app/runtime/deps.py`. No change to routes, the application service,
stages, contracts, or the frontend. Reasoning automatically switches from
`evidence_fallback` to full graph-based reasoning.

---

## 5. Technical debt

| Item | Impact | Recommended action |
|---|---|---|
| Reasoning runs `evidence_fallback` (graph absent) | Coarser claims; conservative decisions | Land Graph Intelligence |
| `BlueprintRoleDNAProvider` bare skill refs vs shared `skill:` convention | Bridged in adapter | Standardize ref convention with Developer 1 |
| No v2 job/candidate persistence | Frontend sends job context + sources inline | Add a v2 store (keep World A DB separate) |
| 47 `print()` calls in World A / JD / evidence modules | Log hygiene | Migrate to module loggers |
| No explicit app-level logging config | Relies on an import side-effect | Configure logging at startup |
| `requirements.txt` uses `>=` (no lockfile) | Build reproducibility | Add a lockfile |
| Two venvs (`backend/.venv` empty) | Onboarding confusion | Document/standardize the interpreter |
| Two generations (World A + v2) | Larger surface | Plan eventual consolidation post-frontend-migration |

None block integrated development. Full severity table in
[production-readiness-audit.md](production-readiness-audit.md).

---

## 6. Frontend contract

The frontend integrates against **two business endpoints** and never sees a pipeline object.

### `POST /v2/evaluations`
```jsonc
// request
{ "candidate_id": "c1", "job_id": "j1",
  "role_blueprint": { "required_skills": [{"normalized_name": "python"}] },  // or "jd_text"
  "sources": { "github": { /* raw source payload */ } } }
// response (EvaluationResponse)
{ "evaluation_id", "candidate_id", "job_id",
  "recommendation": "hire|lean_hire|strong_hire|no_hire|insufficient_evidence",
  "score": 0.87, "confidence": 0.87, "summary",
  "reasons": [], "reservations": [], "interview_focus": [{"topic","rationale","suggested_questions"}],
  "status": "completed|failed",
  "meta": { "graph_enabled": false, "reasoning_mode": "evidence_fallback", "total_ms", "stages" } }
```

### `POST /v2/rankings`
```jsonc
// request
{ "job_id": "j1", "role_blueprint": {…},        // or "jd_text"
  "candidates": [ { "candidate_id": "c1", "sources": {…} } ], "limit": 100 }
// response (RankingResponse)
{ "job_id", "count", "ranked": [ {"rank","candidate_id","score","recommendation","summary"} ], "meta" }
```

### Guarantees
- Business entities only — no `CandidateGraph` / `RoleDNA` / `Evidence` / `CandidateReasoning`.
- Validated requests (422 when neither `jd_text` nor `role_blueprint` is supplied).
- Never 5xx on bad/empty/failed sources — a decision is always returned; one bad candidate
  never fails a ranking batch.
- Deterministic for identical input.
- Honest degradation surfaced via `meta.graph_enabled` / `meta.reasoning_mode`.
- Documented in Swagger (`v2: evaluations`); per-stage endpoints tagged `v2: internal/debug`.

**Caveat:** until v2 persistence exists, the frontend supplies job context + candidate
source payloads inline.

---

## 7. Deployment readiness

**Present:** `/health`; Alembic migrations; `docker-compose.yml` provisioning
postgres/redis/qdrant; centralized `Settings` with `.env`/`.env.local` layering; secrets
gitignored (none committed); CORS configurable; `debug` now defaults `False`.

**Gaps (operational, not architectural):**
- No Dockerfile / compose service for the API (recommended one in the audit).
- No authn/authz on `/v2/*` — add before public exposure.
- No explicit logging configuration at startup.
- No dependency lockfile.
- No v2 persistence layer.

**Scores:** Backend **88/100** · Frontend **90/100** · Production **70/100**
(rationale in the production readiness audit).

---

## 8. Production roadmap

**P0 — harden for staging (operational)**
1. Backend Dockerfile + `api` compose service (`DEBUG=false`, env-injected secrets).
2. Authn/authz on `/v2/*`.
3. Explicit logging config at startup; migrate World A `print()`s to loggers.
4. Dependency lockfile.

**P1 — close functional gaps**
5. v2 job/candidate persistence (separate from World A DB).
6. Structured error/degraded response on single-evaluation hard failure.
7. Standardize the skill-ref convention with Developer 1 (retire the adapter bridge).

**P2 — Graph Intelligence (Developer 3)**
8. Implement `CandidateGraphAdapter` + real `FusionEngine`; swap them into
   `app/runtime/deps.py`. Reasoning upgrades from `evidence_fallback` to graph-based with
   zero API/runtime/contract change.

**P3 — consolidation**
9. Plan World A → v2 migration once the frontend is on `/v2/*`; move stage endpoints under
   `/v2/debug/`; address remaining tech debt.

---

## 9. Final status

The DELULU v2 backend is **integrated, tested, stable, and ready for frontend
development**. It runs the full hiring pipeline end-to-end using Role DNA, Evidence
Providers, the Reasoning Engine, the Decision Engine, the Deterministic Ranking Engine, and
explainability — and is fully compatible with the future Graph Intelligence implementation
via the `NoOpGraphAdapter` seam. 293/293 tests pass; no shared contracts, World A code, or
developer engine implementations were modified.
