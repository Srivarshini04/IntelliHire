# DELULU v2 — Architecture (Evidence OS)

DELULU v2 is a **reasoning-first** candidate-ranking platform. Where a score-first
system computes a number and back-fills a justification, v2 produces a *defensible
judgment* first and projects a number out of it only at the end. Every cross-module
contract lives in `app.shared` (the single source of truth); nothing redefines a
contract locally.

---

## 1. Layered architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Sources / Documents      resume JSON · GitHub · LinkedIn · LeetCode ·     │
│                           Redrob signals · portfolio · manual              │
├──────────────────────────────────────────────────────────────────────────┤
│  L1  Evidence layer       EvidenceProvider*  ──▶  list[Evidence]           │
│                           (one observed fact, one source, one entity)      │
├──────────────────────────────────────────────────────────────────────────┤
│  L2  Knowledge layer      GraphBuilder + entity_resolver ──▶ CandidateGraph│
│                           FusionEngine ──▶ fused GraphNode.confidence       │
├──────────────────────────────────────────────────────────────────────────┤
│  L3  Reasoning layer      ReasoningEngine(CandidateGraph + RoleDNA)        │
│                           ──▶ CandidateReasoning  (the moat)               │
├──────────────────────────────────────────────────────────────────────────┤
│  L4  Decision layer       DecisionEngine ──▶ HiringDecision                │
│                           (derived_score is a projection, not the source)  │
├──────────────────────────────────────────────────────────────────────────┤
│  L5  Ranking layer        RankingEngine.retrieve ──▶ rerank                │
│                           ──▶ CandidateRanking / RankedList (the 100 rows) │
├──────────────────────────────────────────────────────────────────────────┤
│  L6  Surfacing            Explainability / Dashboard                       │
└──────────────────────────────────────────────────────────────────────────┘
        Role side:  Job/JD/RoleBlueprint ──▶ RoleDNAProvider ──▶ RoleDNA
        Carrier:    app.shared.context.PipelineContext threads all layers
```

The canonical contracts (all frozen in `app.shared`):

| Layer | Interface (`app.shared.interfaces`) | Output model (`app.shared.models`) |
|-------|-------------------------------------|------------------------------------|
| Evidence | `EvidenceProvider` | `Evidence` |
| Role | `RoleDNAProvider` | `RoleDNA` |
| Graph | `GraphBuilder` | `CandidateGraph` (`GraphNode`, `GraphEdge`, `EvidenceLedgerEntry`) |
| Fusion | `FusionEngine` | `CandidateGraph` (with `GraphNode.confidence` set) |
| Reasoning | `ReasoningEngine` | `CandidateReasoning` (`ReasoningClaim`, `CandidateGap`) |
| Decision | `DecisionEngine` | `HiringDecision` (`Recommendation`, `InterviewFocus`) |
| Ranking | `RankingEngine` | `CandidateRanking`, `RankedList` |

---

## 2. The pipeline and the exact shared object per hop

```
Sources ──▶ EvidenceProvider.collect ─────────▶ list[Evidence]
list[Evidence] ──▶ GraphBuilder.build ────────▶ CandidateGraph
CandidateGraph ──▶ FusionEngine.fuse ─────────▶ CandidateGraph (confidence set)
(CandidateGraph + RoleDNA) ──▶ ReasoningEngine.reason ──▶ CandidateReasoning
(CandidateReasoning + RoleDNA) ──▶ DecisionEngine.decide ──▶ HiringDecision
list[HiringDecision] ──▶ RankingEngine.rerank ──▶ RankedList[CandidateRanking]

Role side:
(job_id, jd_text?, blueprint?) ──▶ RoleDNAProvider.build ──▶ RoleDNA
```

`Evidence` is the atomic unit of the Evidence OS: **one observation, from one
source, about one canonical entity** (`entity_ref`, e.g. `skill:fastapi`). Once a
`CandidateGraph` exists, no downstream engine reads raw resumes or repos again —
reasoning is graph traversal.

---

## 3. The three frozen design decisions

### Decision A — polarity, not subtraction (monotonic fusion)

`Evidence.polarity` is an `EvidencePolarity` ∈ `{SUPPORTS, CONTRADICTS}`.
Contradictions are **recorded**, never arithmetically subtracted. The
`FusionEngine` is **monotonic** over `SUPPORTS` evidence only — adding evidence can
only raise a node's confidence. Conflict resolution (`SUPPORTS` vs `CONTRADICTS`)
happens **exclusively** in the `ReasoningEngine`, where counter-evidence surfaces on
`ReasoningClaim.counter_evidence_ids`.

*Rationale:* subtractive fusion entangles "this source is weak" with "this source
disagrees," producing scores nobody can defend. Keeping fusion monotonic makes node
confidence a clean probability-of-support; judgment about conflicts is a reasoning
concern, made once, with full context.

### Decision B — materiality is role-relative, computed in reasoning

Importance is **never** stored on `Evidence`. `ReasoningClaim.materiality` is an
`Intensity` derived at reason time from `RoleDNA` (its `capability_weights` and the
behavioural `Intensity` fields like `ownership_level`, `system_design_expectation`).

*Rationale:* the same fact ("built a CLI tool") is critical for one role and
irrelevant for another. Pinning importance to evidence would force re-extraction per
job and make providers role-aware. Keeping providers role-agnostic makes them
reusable across every job; only reasoning knows the role.

### Decision C — absence is computed, never emitted

Providers emit only **observed** facts. "No Kubernetes" is never an `Evidence`
object. Gaps are derived in reasoning by diffing the `CandidateGraph` against
`RoleDNA` (e.g. `must_have_skills` not present as nodes), surfaced as
`CandidateGap` with a `GapSeverity` ∈ `{MINOR, MODERATE, BLOCKING}`.

*Rationale:* absence is meaningful only relative to a requirement, and requirements
live in `RoleDNA`. A provider cannot know what's missing without the role; reasoning
can. This keeps the evidence layer honest (it asserts only what it saw).

---

## 4. Two-stage ranking (forced by scale)

The challenge pool is **100,000 candidates**; the submission is **exactly 100
ranked rows**. A single LLM pass over 100k is infeasible, so `RankingEngine` is a
coarse-to-fine funnel (`RankingStage`):

1. **`retrieve` — STAGE 1 (`RETRIEVAL`).** Cheap, deterministic, vectorized scoring
   over the **full pool**, **no LLM**. Input: `job_id`, `RoleDNA`, raw candidate
   dicts, `top_k`. Output: `list[CandidateRanking]` (`stage=RETRIEVAL`). Produces a
   shortlist (`DEFAULT_RETRIEVAL_TOP_K = 300`) worth reasoning about.
2. **`rerank` — STAGE 2 (`RERANK`).** Reasoning-based fine ranking over the
   shortlist's `HiringDecision`s. Input: `job_id`, `list[HiringDecision]`, `limit`
   (`SUBMISSION_SIZE = 100`). Output: `RankedList` of `CandidateRanking`, each
   carrying the required free-text `reasoning` column and a `decision_ref` back to
   its `HiringDecision`.

Only the ~300 shortlisted candidates pay the full Evidence→Graph→Reasoning→Decision
cost; the other ~99,700 are eliminated cheaply and deterministically.

---

## 5. Why reasoning-first beats score-first

- **Defensibility.** Every ranked row traces to a `HiringDecision` →
  `CandidateReasoning` → `ReasoningClaim`s → `Evidence` → `provenance`/`source_span`.
  The number is a consequence of the argument, not a substitute for it.
- **Honest conflicts and gaps.** Decisions A and C mean contradictions and absences
  are first-class reasoning objects, not noise buried in a weighted sum.
- **Role portability.** Decision B keeps extraction role-agnostic; re-running for a
  new role only re-runs reasoning, not the whole stack.
- **Auditability.** `derived_score` is explicitly a *projection* of reasoning
  (`HiringDecision.derived_score`), so the scalar and the rationale can never drift
  apart.

---

## 6. Single source of truth

Every module imports its contracts from `app.shared`:

```python
from app.shared.models import Evidence, CandidateGraph, RoleDNA, HiringDecision
from app.shared.interfaces import EvidenceProvider, ReasoningEngine
from app.shared.enums import EvidencePolarity, EvidenceSource, Intensity
from app.shared.constants import SOURCE_WEIGHTS
```

`SOURCE_WEIGHTS` (per-source trust used by probability-of-support fusion) lives in
`app.shared.constants` — not in `confidence_fusion` — so the dependency points the
correct direction (`intelligence` depends on `shared`, never the reverse). There is
exactly one definition of each contract in the repository.
