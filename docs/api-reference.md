# DELULU v2 — API Reference

Six v2 endpoints, one per pipeline stage. All are mounted under the `/v2` prefix
(`app.api.v2.router` exposes `APIRouter(prefix="/v2")`).

**Conventions**

- **Request models** (`app.api.v2.schemas`) are *new input contracts*. They **omit
  server-generated ids** (`graph_id`, `role_dna_id`, `reasoning_id`, `decision_id`,
  `ranking_id`, `ranked_list_id`) — the server assigns those.
- **Response models** are the frozen shared domain models from `app.shared.models`,
  imported directly by the routers (never duplicated).
- Every route uses the standard `ERROR_RESPONSES` envelope (`ErrorResponse`:
  `code`, `message`, `details?`) for 400 / 404 / 422 / 500.

| # | Method & path | Stage | Request | Response |
|---|---------------|-------|---------|----------|
| 1 | `POST /v2/evidence/extract` | `EvidenceProvider` | `ExtractEvidenceRequest` | `ExtractEvidenceResponse` |
| 2 | `POST /v2/graph/build` | `GraphBuilder` (+`FusionEngine`) | `BuildGraphRequest` | `CandidateGraph` |
| 3 | `POST /v2/role-dna/generate` | `RoleDNAProvider` | `GenerateRoleDNARequest` | `RoleDNA` |
| 4 | `POST /v2/reasoning/run` | `ReasoningEngine` | `RunReasoningRequest` | `CandidateReasoning` |
| 5 | `POST /v2/decision/generate` | `DecisionEngine` | `GenerateDecisionRequest` | `HiringDecision` |
| 6 | `POST /v2/ranking/rank` | `RankingEngine` (two-stage) | `RankCandidatesRequest` | `RankedList` |

---

## 1. `POST /v2/evidence/extract`

Turn one raw source payload into atomic `Evidence` (observed facts only — never
absence, no role weighting).

**Request — `ExtractEvidenceRequest`**

```json
{
  "candidate_id": "CAND_0000001",
  "source": "github",
  "raw": { "repository": "ClinicBot", "commits": 214, "files": 61 }
}
```
- `source` is an `EvidenceSource` enum value (`resume`, `github`, `linkedin`,
  `leetcode`, `portfolio`, `kaggle`, `huggingface`, `gitlab`, `redrob`, `manual`).

**Response — `ExtractEvidenceResponse`**

```json
{
  "candidate_id": "CAND_0000001",
  "source": "github",
  "evidence": [ { "...Evidence..." } ]
}
```
Each item is a full `Evidence` (`evidence_id`, `entity_ref`, `claim`, `polarity`,
`confidence`, `provenance`, `source_span?`, `verification_status`).

---

## 2. `POST /v2/graph/build`

Assemble fused `Evidence` into a `CandidateGraph` (canonicalize entities, create
nodes/edges, write the evidence ledger). Server assigns `graph_id`.

**Request — `BuildGraphRequest`**

```json
{
  "candidate_id": "CAND_0000001",
  "evidence": [ { "...Evidence..." } ],
  "job_id": "j1"
}
```
- `evidence` must be non-empty (`min_length=1`). `job_id` is optional — set when the
  graph is scoped to a specific role.

**Response — `CandidateGraph`** (`graph_id`, `candidate_id`, `job_id?`, `nodes`,
`edges`, `evidence_ledger`, `metadata`). `GraphNode.confidence` is populated by the
fusion step.

---

## 3. `POST /v2/role-dna/generate`

Derive rich hiring intent (`RoleDNA`) from a JD and/or `RoleBlueprint`. Server
assigns `role_dna_id`.

**Request — `GenerateRoleDNARequest`**

```json
{
  "job_id": "j1",
  "jd_text": "We need a senior backend engineer ...",
  "blueprint": null
}
```
- At least one of `jd_text` or `blueprint` is required (model validator).

**Response — `RoleDNA`** (`role_dna_id`, `job_id`, `role_summary`,
`must_have_skills`, `nice_to_have_skills`, the behavioural `Intensity` fields,
`capability_weights`, `required_evidence`, …).

---

## 4. `POST /v2/reasoning/run`

Reason over a `CandidateGraph` against `RoleDNA`. Server assigns `reasoning_id`.

**Request — `RunReasoningRequest`**

```json
{
  "candidate_id": "CAND_0000001",
  "job_id": "j1",
  "graph_id": "graph:c1:j1",
  "role_dna_id": "roledna:j1"
}
```

**Response — `CandidateReasoning`** (`reasoning_id`, `claims` of `ReasoningClaim`,
`gaps` of `CandidateGap`, `uncertainties`, `overall_confidence`, `summary`).
Decisions A/B/C surface here: `counter_evidence_ids`, `materiality`, and `gaps`.

---

## 5. `POST /v2/decision/generate`

Project `CandidateReasoning` into a recruiter-facing `HiringDecision`. Server assigns
`decision_id`.

**Request — `GenerateDecisionRequest`**

```json
{
  "candidate_id": "CAND_0000001",
  "job_id": "j1",
  "reasoning_id": "reasoning:c1:j1",
  "role_dna_id": "roledna:j1"
}
```

**Response — `HiringDecision`** (`decision_id`, `recommendation`
(`RecommendationLevel`), `confidence`, `derived_score`, `reasons`, `reservations`,
`interview_focus`, `recommendations`, `summary`). `derived_score` is a projection of
the reasoning and feeds the reranker.

---

## 6. `POST /v2/ranking/rank`

Two-stage ranker. Server assigns `ranked_list_id` and per-row `ranking_id`s.

**Request — `RankCandidatesRequest`** (`stage` selects the inputs):

`stage = "retrieval"` (STAGE 1, cheap/vectorized/no-LLM over the full pool):
```json
{
  "job_id": "j1",
  "stage": "retrieval",
  "role_dna_id": "roledna:j1",
  "candidates": [ { "candidate_id": "CAND_0000001", "...raw dict..." } ],
  "top_k": 300
}
```

`stage = "rerank"` (STAGE 2, reasoning-based over the shortlist):
```json
{
  "job_id": "j1",
  "stage": "rerank",
  "decisions": [ { "...HiringDecision..." } ],
  "limit": 100
}
```
- Validators: `RETRIEVAL` requires `candidates` + `role_dna_id`; `RERANK` requires
  `decisions`. `top_k` defaults to `DEFAULT_RETRIEVAL_TOP_K` (300); `limit` defaults
  to `SUBMISSION_SIZE` (100), server-side.

**Response — `RankedList`** (`ranked_list_id`, `job_id`, `stage`, `items` of
`CandidateRanking`). Each `CandidateRanking` carries `rank`, `score`, `stage`, the
required free-text `reasoning` column, and `decision_ref` (set when
`stage == RERANK`). The `RERANK` items are the rows submitted to the challenge.
