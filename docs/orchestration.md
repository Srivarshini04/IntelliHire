# DELULU v2 — Orchestration Layer

> Owner: Tech Lead (Developer 1). This layer connects the platform together
> **through the frozen shared interfaces only**. It contains no evidence, graph,
> reasoning, decision, or ranking-intelligence logic — those belong to the other
> developers and are injected as interface implementations.

---

## 1. Where it sits

```
Job Description ──► RoleBlueprint ──►  RoleDNA  ─────────────┐  (role side)
 (Job Intelligence — existing)     (RoleDNAProvider, owned)  │
                                                             ▼
Candidate raw sources ─► EvidenceProvider ─► GraphBuilder ─► FusionEngine ─►
                         ReasoningEngine ─► DecisionEngine ─► HiringDecision
                         └──────────────── PipelineRuntime ────────────────┘
                                                             │
                                          RankingOrchestrator + RankingEngine
                                                             ▼
                                                        RankedList
```

Owned modules (this layer): **Role DNA**, **PipelineRuntime**, stage adapters,
**CandidateEvaluationPipeline**, **RankingOrchestrator**, **BaselineRankingEngine**,
**deps**, and the **API wiring** of `/v2/role-dna/generate` and `/v2/ranking/rank`.

Injected (other developers, via frozen Protocols): `EvidenceProvider`,
`GraphBuilder`, `FusionEngine`, `ReasoningEngine`, `DecisionEngine` — and any
future production `RankingEngine`.

---

## 2. Components

| Component | File | Role |
|---|---|---|
| `BlueprintRoleDNAProvider` | `app/intelligence/role_dna/role_dna_provider.py` | Implements frozen `RoleDNAProvider`. Deterministic enrichment `RoleBlueprint → RoleDNA` (no LLM). |
| Role DNA inference | `app/intelligence/role_dna/inference.py` | Pure helpers: engineering level, behavioural `Intensity`, summary/success-profile/interview-focus synthesis. |
| `Stage` / `StageInputError` | `app/runtime/stage.py` | Stage contract (read/write `PipelineContext`). |
| `PipelineRuntime` / `StageError` | `app/runtime/pipeline_runtime.py` | Generic async executor: ordering, timing, telemetry, error/cancellation propagation. |
| Stage adapters | `app/runtime/stages.py` | `EvidenceStage`, `GraphStage`, `FusionStage`, `ReasoningStage`, `DecisionStage` — glue over the interfaces. |
| `CandidateEvaluationPipeline` | `app/runtime/candidate_evaluation_pipeline.py` | Per-candidate chain → `HiringDecision`. |
| `RankingOrchestrator` | `app/runtime/ranking_orchestrator.py` | Batch: evaluate each candidate → rerank. |
| `BaselineRankingEngine` | `app/runtime/ranking_engine.py` | Deterministic-only `RankingEngine` (runtime infra). |
| `deps` | `app/runtime/deps.py` | FastAPI providers — the single swap-point for real engines. |

---

## 3. Data flow — the exact object at each hop

All objects are the **canonical shared models** (`app.shared.models`); nothing is
redefined. The orchestrator threads them through `app.shared.context.PipelineContext`.

| Stage | Reads from context | Writes to context |
|---|---|---|
| `EvidenceStage` | `raw_sources`, `candidate_id` | `evidence: list[Evidence]` |
| `GraphStage` | `evidence` | `graph: CandidateGraph` |
| `FusionStage` | `graph` | `graph` (node confidence fused) |
| `ReasoningStage` | `graph`, `role_dna` | `reasoning: CandidateReasoning` |
| `DecisionStage` | `reasoning`, `role_dna` | `decision: HiringDecision` |
| `RankingOrchestrator` | `HiringDecision[]` | `RankedList` (`CandidateRanking[]`) |

Per-stage timing + status land in `ctx.telemetry["stages"][<name>]`; total wall
time in `ctx.telemetry["total_ms"]`.

---

## 4. Approved decisions encoded here

- **Decision A** — `Evidence.polarity` carries supports/contradicts; fusion stays
  monotonic; conflict resolution is the ReasoningEngine's job (not this layer's).
- **Decision B** — materiality is role-relative; computed in reasoning from
  `RoleDNA`, never on `Evidence`.
- **Decision C** — absence/gaps are produced by reasoning (`CandidateGap`); never
  emitted by providers.
- **RoleDNA Option A** — `leadership_expectation`, `success_profile`,
  `interview_focus`, `risk_tolerance` live in `RoleDNA.metadata`. The shared
  `RoleDNA` contract is **unchanged**.
- **BaselineRankingEngine (Decision 2)** — deterministic only. `rerank()` sorts
  `HiringDecision.derived_score`; `retrieve()` is an order-preserving shortlist
  (positional placeholder score, **not** a quality score). No LLM/AI/heuristics/
  learning/optimization.
- **Decision 3** — RoleDNA is generated on demand; no new persistence/table/cache.
- **Decision 4** — boundary: per-candidate `CandidateEvaluationPipeline.evaluate →
  HiringDecision`; batch `RankingOrchestrator → RankedList`.

---

## 5. How the other developers plug in

No change to this layer is required. Implement the frozen Protocol, then register
it in `app/runtime/deps.py`.

```python
# 1. Your module implements the interface (structural typing — just match the methods):
class RealGraphBuilder:                      # satisfies app.shared.interfaces.GraphBuilder
    async def build(self, candidate_id, evidence, job_id=None) -> CandidateGraph: ...

# 2. Wire it where the pipeline is assembled (deps.py / a factory):
CandidateEvaluationPipeline(
    evidence_providers=[RealResumeProvider(), RealGithubProvider(), ...],
    graph_builder=RealGraphBuilder(),
    fusion_engine=RealFusionEngine(),
    reasoning_engine=RealReasoningEngine(),
    decision_engine=RealDecisionEngine(),
)
```

Until then, the deterministic test doubles in `tests/mocks/` exercise the full
chain. The API today serves:
- `POST /v2/role-dna/generate` → real `BlueprintRoleDNAProvider` (ready now).
- `POST /v2/ranking/rank` → `BaselineRankingEngine` (`RETRIEVAL` shortlist /
  `RERANK` of supplied `HiringDecision[]`).

The full candidate→decision API path goes live the moment the five engines are
registered in `deps.py` (then `RankingOrchestrator` can back `/v2/ranking/rank`).

---

## 6. Run & test

```bash
cd backend
pip install -r requirements-dev.txt          # pytest
python -m pytest tests/ -q                    # full suite (48 passing)
python -m pytest tests/test_candidate_evaluation_pipeline.py -q   # e2e only
```

Tests follow the repo convention (plain `pytest` + `asyncio.run`, no async
markers, no `conftest`).

---

## 7. Acceptance criteria → where met

| Criterion | Met by |
|---|---|
| Role DNA deterministically enriches RoleBlueprint | `BlueprintRoleDNAProvider` + `inference.py`; `test_role_dna_provider.py` |
| Runtime executes all stages through interfaces | `PipelineRuntime` + `stages.py`; `test_pipeline_runtime.py` |
| CandidateEvaluationPipeline → HiringDecision | `candidate_evaluation_pipeline.py`; `test_candidate_evaluation_pipeline.py` |
| RankingOrchestrator → RankedList via BaselineRankingEngine | `ranking_orchestrator.py` + `ranking_engine.py` |
| API routes wired | `routes/role_dna.py`, `routes/ranking.py`, `deps.py` |
| Tests pass | 19 orchestration + 48 total |
| No shared contracts changed | `git diff` on `app/shared/` is empty |
| No overlap with other developers | engines injected via Protocols only |
| Production-ready & pluggable | deterministic, typed, documented, async throughout |
