# DELULU v2 — Phase 7 Production Readiness Audit

**Branch:** `develop` @ `721784c` (uncommitted integration work)
**Scope:** Audit-only. Fixes limited to genuine issues; no architectural redesign.
**Method:** static scans (imports, AST unused-symbol, secrets, prints, TODOs), config &
dependency review, API/OpenAPI consistency, security & deployment sanity, 293-test run.

---

## 1. Issues found

Severity: **Critical** (block release) · **High** · **Medium** · **Low** · **Info** (no action).

| ID | Area | Issue | Severity | Recommended fix | Status |
|---|---|---|---|---|---|
| S1 | Security | `/v2/*` endpoints have no authn/authz | **Medium** | Apply auth (reuse `app.core.security`) before exposing publicly | Recommended |
| S2 | Security | CORS `allow_methods/headers=["*"]` with credentials | Low | Restrict in prod via env; origins already configurable | Recommended |
| S3 | Security/Config | `debug` defaulted `True` → SQLAlchemy SQL echo on by default | Low | Default `False`; opt in via `DEBUG=true` | **Fixed** |
| S4 | Security | Secrets via env; `.env` + `*.db` gitignored; none committed | Info | — | Pass |
| C1 | Config | No v2 job/candidate persistence (context sent inline) | Medium | Add a v2 store later (World A DB is off-limits) | By design |
| C2 | Config | Centralized `Settings`, `.env`/`.env.local` layering, `.env.example` present | Info | — | Pass |
| L1 | Logging | No explicit app-level logging config; relies on a `logging.basicConfig` import side-effect in `app/pipeline/orchestrator.py` | Low | Configure logging explicitly in `main` startup | Recommended |
| L2 | Logging | 47 `print()` calls in World A / JD / evidence modules | Low | Convert to module loggers | Recommended (not v2 path) |
| D1 | Dead code | ~19 modules with no internal importer | Info | Mostly World A, D3 graph scaffolding, Celery placeholder, or false positives (`from pkg import submodule`). None on the v2 path | No action |
| D2 | Dead code | `get_deterministic_ranking_engine` alias now unused | Low | Kept as documented back-compat alias; optional removal | Accepted |
| A1 | API | v2 routes: `response_model` + `status_code` + `ERROR_RESPONSES` consistent; primary vs internal/debug tags correct | Info | — | Pass |
| A2 | API | `/v2/evaluations` (single) would return 500 on a hard pipeline failure (uses `fail_fast`) | Low | Wrap for a structured/degraded response | Recommended (low likelihood) |
| A3 | API | Stage endpoints under `/v2/*` (not `/v2/debug/`) | Cosmetic | Agreed future task — **intentionally not changed** | Deferred |
| Dep1 | Deployment | No Dockerfile for the API; compose provisions only infra (postgres/redis/qdrant) | **Medium** | Add a backend Dockerfile + an `api` compose service | Recommended |
| Dep2 | Deployment | `/health` present; Alembic migrations present | Info | — | Pass |
| Dep3 | Deployment | Two venvs (`backend/.venv` lacks deps; root `.venv` is the working one) | Low | Standardize/document the interpreter | Recommended |
| Dep4 | Deployment | `requirements.txt` uses `>=` (no upper pin / lockfile) | Low | Add a lockfile for reproducible builds | Recommended |
| T1 | Tech debt | Reasoning runs `evidence_fallback` until Graph Intelligence lands | Info | Resolves when `CandidateGraphAdapter` replaces `NoOpGraphAdapter` in DI | By design |
| T2 | Tech debt | `BlueprintRoleDNAProvider` emits bare skill refs vs shared `skill:` convention | Low | Standardize with Developer 1; bridged in the adapter today | Recommended |
| T3 | Tech debt | Two generations coexist (World A `/api` + v2) | Info | Intentional; v2 is additive and isolated | No action |

**No Critical or High issues.** The integration code authored in Phases 2–5 has **no
dead imports** (AST-checked) and **no circular dependencies**; all 211 modules import; 293
tests pass.

---

## 2. Fixes applied this phase

| Fix | File | Why |
|---|---|---|
| `debug` default `True → False` | `app/core/config.py` | Production-safe default; SQL echo no longer on unless `DEBUG=true` is set. Verified: dev `.env` still opts in; 293 tests pass. |

Only one change — the single clear, in-scope production issue. Everything else is either
in off-limits modules (World A / other developers), by design (no v2 persistence, graph
absent), or a recommendation requiring a decision (auth, Dockerfile).

---

## 3. Deployment recommendation (not applied — provided for the team)

A backend Dockerfile + compose service is the main deployment gap. Recommended:

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

…plus an `api` service in `docker-compose.yml` depending on `postgres`/`redis`/`qdrant`,
with `DEBUG=false` and real secrets injected via environment.

---

## 4. Readiness scores

### Backend readiness — **88 / 100**
Runs end-to-end; clean DI; graceful degradation; concurrency-safe; deterministic; 293
tests; no broken/circular imports; anti-corruption layer isolates developer modules.
*Deductions:* reasoning is `evidence_fallback` until Graph Intelligence (−6); no v2
persistence (−4); single-evaluation hard-failure returns 500 (−2).

### Frontend readiness — **90 / 100**
Stable, validated, business-oriented API (`/v2/evaluations`, `/v2/rankings`); no pipeline
objects exposed; documented in Swagger; honest degradation via `meta`.
*Deductions:* job context + sources sent inline pending v2 persistence (−6); reasoning
fidelity limited until graph lands (−4).

### Production readiness — **70 / 100**
Functionally complete and stable, but not yet hardened/containerized.
*Deductions:* no app Dockerfile/compose service (−10); no authn/authz on `/v2/*` (−8);
no explicit logging config (−4); unpinned deps / no lockfile (−4); no v2 persistence (−4).

---

## 5. Verdict

**Ship-ready for integrated development and internal/staging use; not yet hardened for
public production.** The v2 backend is correct, stable, tested, and cleanly encapsulated.
The remaining gaps to public production are operational (containerization, auth, logging
config, dependency pinning, persistence) — none require architectural change, and all are
captured above with concrete recommendations.
