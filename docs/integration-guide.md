# DELULU v2 — Integration Guide

How the four workstreams plug together, and the order Phase C implements the
business logic behind the frozen interfaces.

## 1. The integration seam: `app.shared` + `PipelineContext`

Everything connects through two things, both frozen in Phase A:

1. **The contracts in `app.shared`** — `models`, `enums`, `interfaces`, `constants`.
   Each workstream imports the same definitions; no one redefines them. This is what
   lets four developers build in parallel without merge collisions on data shapes.
2. **`app.shared.context.PipelineContext`** — the per-`(candidate, job)` carrier the
   orchestrator threads through every stage. Each engine reads the fields it needs
   and writes its output back onto the same object.

```
            ┌─────────────────── app.shared (frozen) ───────────────────┐
            │  models · enums · interfaces (Protocols) · constants       │
            └────┬───────────────┬───────────────┬───────────────┬──────┘
                 │ imports        │ imports       │ imports       │ imports
        ┌────────▼──────┐ ┌───────▼──────┐ ┌──────▼───────┐ ┌─────▼──────┐
        │ persistence   │ │ api (v2)     │ │ mock-data    │ │ docs       │
        │ (repositories)│ │ routes+schem.│ │ fixtures     │ │            │
        └───────────────┘ └──────────────┘ └──────────────┘ └────────────┘
                 │                 │                 │
                 └──────── all read/write the same PipelineContext ───────┘
```

- **api** exposes one endpoint per stage; its request schemas embed shared models
  and omit server-assigned ids; its responses *are* the shared models.
- **persistence** stores/loads the shared models (graphs, reasonings, decisions,
  rankings) — keyed by the stable ids the contracts define.
- **mock-data** produces `raw_sources` payloads and sample candidates shaped to the
  enums/models so the pipeline can run end-to-end before real providers exist.
- **docs** describes the contracts and flow (this folder).

## 2. End-to-end integration sequence

```
1. RoleDNAProvider.build(job_id, jd_text?, blueprint?)        → ctx.role_dna
2. for each source:  EvidenceProvider.collect(cid, raw)       → ctx.evidence += [...]
3. GraphBuilder.build(cid, ctx.evidence, job_id)              → ctx.graph
4. FusionEngine.fuse(ctx.graph)                              → ctx.graph (confidence set)
5. ReasoningEngine.reason(ctx.graph, ctx.role_dna)           → ctx.reasoning
6. DecisionEngine.decide(ctx.reasoning, ctx.role_dna)        → ctx.decision
7. RankingEngine.retrieve(job_id, role, pool, top_k)         → shortlist (stage 1, no LLM)
   … run steps 2–6 for each shortlisted candidate …
   RankingEngine.rerank(job_id, [HiringDecision], limit)     → RankedList (stage 2)
8. Explainability / Dashboard / submission CSV               ← traces back through ctx
```

The two-stage funnel (step 7) is what makes 100k candidates tractable: `retrieve`
runs cheaply over the **full pool** to pick ~300 (`DEFAULT_RETRIEVAL_TOP_K`); only
those pay the full Evidence→Graph→Reasoning→Decision cost before `rerank` emits the
final 100 (`SUBMISSION_SIZE`), each row carrying the required `reasoning` text and a
`decision_ref`.

## 3. Phase C — order of implementing the business logic

Phase A froze the contracts and Protocols (no logic). Phase C fills in the
implementations behind each `app.shared.interfaces` Protocol, in dependency order so
each stage can be tested against real upstream output:

1. **`EvidenceProvider`** (per source: resume, github, redrob, …). Foundation of
   everything — emits `Evidence` (observed facts only; Decision C). Start with the
   Redrob/resume providers since the challenge dataset is pre-structured.
2. **`RoleDNAProvider`** (parallel to 1, role side). Produces `RoleDNA` — the basis
   for materiality (Decision B) and gap detection (Decision C).
3. **`GraphBuilder`** (+ `entity_resolver`). Canonicalizes entities and assembles the
   `CandidateGraph` + evidence ledger. Deterministic, no scoring.
4. **`FusionEngine`** (`confidence_fusion.fuse_confidence`, probability-of-support,
   monotonic over `SUPPORTS`; Decision A). Populates `GraphNode.confidence` using
   `SOURCE_WEIGHTS`.
5. **`ReasoningEngine`** — the moat. Resolves `SUPPORTS` vs `CONTRADICTS`, computes
   role-relative materiality (B), diffs graph vs `RoleDNA` for gaps (C). Needs 3, 4,
   and 2 in place.
6. **`DecisionEngine`** — projects `CandidateReasoning` into a `HiringDecision`
   (recommendation + `derived_score`). Needs 5.
7. **`RankingEngine`** — `retrieve` (stage 1, can ship early since it only needs
   `RoleDNA` + raw dicts) then `rerank` (stage 2, needs the `HiringDecision`s from
   6). Emits the submitted `CandidateRanking` rows.

Rule of thumb: a stage is "integration-ready" when it accepts the exact shared model
its upstream produces and returns the exact shared model its downstream expects — at
which point it can be swapped in behind its Protocol without touching any other
workstream.
