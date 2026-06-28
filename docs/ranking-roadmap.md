# DELULU v2 — Ranking Engine Roadmap

The ranking engine is the one place where DELULU's intelligence is **not yet**
implemented. The current `DeterministicRankingEngine` is **intentionally temporary
infrastructure** — it provides stable, deterministic ordering so the pipeline and
API function while the real ranking intelligence is built.

Every stage below implements the **same frozen `RankingEngine` interface**
(`retrieve()` + `rerank()`), so swapping engines never touches the `PipelineRuntime`,
`RankingOrchestrator`, API routes, or any shared contract — only the injected
instance in `app/runtime/deps.py` changes.

---

## Evolution path

```
Stage 1   DeterministicRankingEngine     sort only (derived_score); no intelligence   ◄── we are here
   │
   ▼
Stage 2   EvidenceAwareRankingEngine     weighted evidence (RoleDNA.capability_weights)
   │
   ▼
Stage 3   ReasoningRankingEngine         compares CandidateReasoning across candidates
   │
   ▼
Stage 4   HybridRankingEngine            rules + reasoning
   │
   ▼
Stage 5   LearningToRankEngine           feedback-optimized (learning-to-rank)
   │
   ▼
Future    LLM Ranking · Graph Ranking · Neural Ranking · Agentic Ranking
```

---

## Stage detail

| Stage | Engine | What it adds | Inputs it leverages |
|---|---|---|---|
| 1 | `DeterministicRankingEngine` | Stable sort by `HiringDecision.derived_score`; order-preserving `retrieve` | `HiringDecision` only |
| 2 | `EvidenceAwareRankingEngine` | Weighted scoring over evidence/capabilities | `CandidateGraph`, `RoleDNA.capability_weights` |
| 3 | `ReasoningRankingEngine` | Cross-candidate comparison of reasoning + gaps | `CandidateReasoning` |
| 4 | `HybridRankingEngine` | Deterministic rules + reasoning signals combined | rules + `CandidateReasoning` |
| 5 | `LearningToRankEngine` | Optimizes ranking from recruiter/outcome feedback | labelled feedback |
| Future | LLM / Graph / Neural / Agentic | Learned and/or generative ranking | full evidence graph + history |

---

## Why deterministic first

- **Unblocks everyone.** The orchestration layer, routes, and tests need *a*
  `RankingEngine` to exist. A deterministic one is the smallest thing that works.
- **Interface-stable.** Because it implements the frozen interface, every later
  engine is a drop-in replacement — no upstream rewrites, no contract churn.
- **Honest naming.** It is named `DeterministicRankingEngine` (not "Baseline") so
  no one mistakes infrastructure for DELULU's ranking algorithm. It does **no**
  intelligence: `rerank` is a pure sort, `retrieve` is a pure shortlist.

The current engine is intentionally temporary and is expected to be replaced.

---

## How to introduce a new ranking engine

1. Implement the frozen `RankingEngine` protocol (`retrieve` + `rerank`) in a new
   class (e.g. `EvidenceAwareRankingEngine`).
2. Swap the injection in `app/runtime/deps.py`
   (`get_deterministic_ranking_engine` → your provider), or add a new provider and
   point the route's `Depends(...)` at it.
3. Done. `PipelineRuntime`, `RankingOrchestrator`, `CandidateEvaluationPipeline`,
   the API routes, and `app.shared` are unchanged.

> Constraint reminder: ranking that uses LLM/AI/heuristics/learning belongs to a
> *new* engine class behind the interface — it must never be added to
> `DeterministicRankingEngine`, which stays deterministic forever.
