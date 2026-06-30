# DELULU v2 — Adapter Conversion Report

Field-level documentation of every translation performed by the anti-corruption layer
(`app/runtime/adapters/`). For each adapter:

- **Mapped** — copied/transformed 1:1 from a source field.
- **Synthesized** — produced by the adapter (no source field).
- **Ignored** — present on the source, intentionally not carried.
- **Information loss** — what fidelity is reduced and why it is safe.

Legend for sources: **EO** = `EvidenceObject` (Dev 2), **RR** = `ReasoningResult` (Dev 4),
**DR** = `DecisionResult` (Dev 4), **CR** = `CandidateReasoning` (shared).

---

## 1. EvidenceProviderAdapter — `EvidenceObject` → `list[Evidence]`

Each `EvidenceObject` becomes *N* `Evidence`: one `SKILL` per detected skill + one
`ASSESSMENT` summary. A failed/empty source (`obj.ok == False`) → `[]`.

| Target `Evidence` field | Origin | Kind |
|---|---|---|
| `evidence_id` | `f"ev:{source}:{candidate_id}:skill:{slug}"` / `:summary` | Synthesized |
| `candidate_id` | adapter argument | Mapped |
| `source` | `EvidenceSource(self.source)` | Mapped (str→enum) |
| `evidence_type` | `SKILL` (per skill) / `ASSESSMENT` (summary) | Synthesized |
| `entity_ref` | `f"skill:{slug(skill)}"` / `f"{source}:{candidate_id}"` | Synthesized (minimal slug) |
| `claim` | `f"{skill} observed in {source}."` / `EO.summary` | Mapped/synthesized |
| `polarity` | `SUPPORTS` (constant) | Synthesized |
| `confidence` | `EO.relevance_score/100` else `EO.reliability` | Mapped (rescaled) |
| `provenance` | `{summary, reliability}` / `{signals, highlights, source_url, processed}` | Mapped |
| `verification_status` | `UNVERIFIED` (constant) | Synthesized |
| `collected_at` | model default (now) | Synthesized |
| `source_span` | — | Synthesized (None) |

**Ignored from EO:** `error` (gates emission, not copied), `raw` (bulky source payload),
`collected_at` (re-stamped), per-skill `EvidenceSignal.value/weight` beyond the summary's
`provenance.signals`.

**Information loss:**
- **Entity resolution** — `entity_ref` is a slug, not a canonical/alias-resolved id
  (that is Developer 3's `entity_resolver`). Skills that differ only by surface form
  (“JS” vs “JavaScript”) will not merge. Safe: downstream matching against `RoleDNA`
  uses the same slug convention; correct resolution arrives with Graph Intelligence.
- **No `CONTRADICTS`** — the adapter emits only `SUPPORTS`; contradiction detection is a
  graph/fusion concern. Safe: monotonic, never invents negatives.
- **Polarity/per-skill confidence flattening** — every skill from one source shares that
  source's confidence. Safe: source-intrinsic, role-agnostic by design (DECISION B).

---

## 2. NoOpGraphAdapter — `list[Evidence]` → `CandidateGraph`

No graph is built. Evidence is passed through on `metadata` for the reasoning fallback.

| Target `CandidateGraph` field | Origin | Kind |
|---|---|---|
| `graph_id` | `f"graph:{candidate_id}[:{job_id}]"` | Synthesized |
| `candidate_id`, `job_id` | arguments | Mapped |
| `nodes`, `edges`, `evidence_ledger` | `[]` | Synthesized (empty) |
| `metadata.graph_disabled` | `True` | Synthesized |
| `metadata.graph_stage` | `"skipped"` | Synthesized |
| `metadata.adapter` / `reason` | constants | Synthesized |
| `metadata.evidence_count` | `len(evidence)` | Mapped |
| `metadata.evidence` | `[ev.model_dump(json) for ev in evidence]` | Mapped (passthrough) |

**Ignored:** nothing — all evidence is carried.

**Information loss:** **all graph structure** — there are no nodes, edges, fused node
confidences, or a bound evidence ledger. This is intentional (Graph Intelligence absent;
Rule 3). Evidence content is preserved verbatim in `metadata.evidence`.

---

## 3. NoOpFusionEngine — `CandidateGraph` → `CandidateGraph`

| Target field | Origin | Kind |
|---|---|---|
| (whole graph) | returned unchanged | Mapped (identity) |
| `metadata.fusion_stage` | `"skipped"` | Synthesized |

**Information loss:** none beyond the absent graph itself — there are no node confidences
to fuse.

---

## 4. ReasoningEngineAdapter — `ReasoningResult` (or evidence) → `CandidateReasoning`

Two paths. **Graph-present:** native `ReasoningResult` → `CandidateReasoning`.
**Graph-disabled:** synthesize claims from `metadata.evidence`, then run Developer 4's
own gap/uncertainty/confidence/summary engines; convert the same way.

| Target `CandidateReasoning` field | Origin | Kind |
|---|---|---|
| `reasoning_id` | `f"reasoning:{candidate_id}:{job_id}"` | Synthesized |
| `candidate_id`, `job_id` | graph/role | Mapped |
| `claims` | `RR.claims` (already `ReasoningClaim`) | Mapped 1:1 |
| `gaps` | `RR.gaps.all_items()` → `CandidateGap` (severity `critical→BLOCKING`, `moderate→MODERATE`, `minor→MINOR`) | Mapped (bucket→enum) |
| `uncertainties` | `RR.uncertainties.all_items()` → `item.rationale or title` | Mapped (object→str) |
| `overall_confidence` | `RR.confidence.overall_confidence` | Mapped |
| `summary` | `RR.summary.overall_summary` | Mapped |
| `metadata.gaps_*` / `uncertainties_*` | bucket counts | Synthesized (for decision rebuild) |
| `metadata.strengths` | `RR.summary.strengths` | Mapped |
| `metadata.confidence_explanation` | `RR.confidence.explanation` | Mapped |
| `metadata.reasoning_mode` | `"evidence_fallback"` (graph-disabled path only) | Synthesized |

**Synthesized in the graph-disabled path (claims from evidence):** `claim_id`,
`statement` (best supporting evidence `claim`), `entity_refs`, `supporting/counter
evidence_ids`, `confidence` (mean support + source-diversity − contradiction penalty),
`materiality` (from RoleDNA), `conclusion`.

**Ignored from RR:** `GapItem.category` / `missing_evidence`, `UncertaintyItem.category` /
`related_entities` / `evidence_count`, `ConfidenceResult.{claim_confidence,
evidence_confidence, uncertainty_penalty}`, `ReasoningSummary.{gaps, uncertainties,
confidence_text}` — these are intermediate detail not on the shared contract.

**Information loss:**
- **Uncertainty objects flattened to strings** — severity is preserved as *counts* in
  `metadata` (so the decision rebuild is faithful), but per-item category/related-entities
  are dropped from the contract surface.
- **Gap detail** — `category`/`missing_evidence` dropped; `requirement`, `severity`,
  `note` retained.
- **Graph-disabled claims are coarser** than graph-based ones (one claim per entity, no
  cross-entity themes like the native `ClaimSynthesizer`'s retrieval/eval/python themes,
  no edge traversal). Safe and intended: real evidence in, no invented structure;
  full-fidelity claims require the Candidate Graph.

---

## 5. DecisionEngineAdapter — `CandidateReasoning` → `HiringDecision`

Rebuilds a native `ReasoningResult` from `CR` (using the stamped metadata counts), calls
Developer 4's untouched `decide()`, maps `DecisionResult` → `HiringDecision`.

| Target `HiringDecision` field | Origin | Kind |
|---|---|---|
| `decision_id` | `f"decision:{candidate_id}:{job_id}"` | Synthesized |
| `candidate_id`, `job_id` | `CR` | Mapped |
| `recommendation` | `DR.recommendation` → `RecommendationLevel` | Mapped (enum→enum) |
| `confidence` | `CR.overall_confidence` (clamped) | Mapped |
| `derived_score` | `DR.score` (clamped) | Mapped |
| `reasons` | `DR.rationale` | Mapped |
| `reservations` | `DR.blockers` | Mapped |
| `interview_focus` | from `CR.gaps` (BLOCKING/MODERATE) → `InterviewFocus` (≤5) | Synthesized |
| `missing_evidence` | `[g.requirement for g in CR.gaps]` | Mapped |
| `recommendations` | `[Recommendation(action=map(level), rationale=DR.next_step)]` | Synthesized |
| `summary` | `CR.summary` else `"; ".join(DR.rationale)` | Mapped |
| `metadata.native_recommendation` / `next_step` | `DR.*` | Mapped |

**Recommendation map:** `strong_hire→STRONG_HIRE`, `hire→HIRE`,
`interview→LEAN_HIRE`, `interview_with_review→LEAN_HIRE`,
`needs_more_information→INSUFFICIENT_EVIDENCE`, `reject→NO_HIRE`.

**Ignored:** native `Recommendation.INTERVIEW` vs `INTERVIEW_WITH_REVIEW` distinction
(both → `LEAN_HIRE`; preserved losslessly in `metadata.native_recommendation`).

**Information loss:**
- **6 native labels → 5 shared levels** — the two interview variants merge into
  `LEAN_HIRE`. Safe: exact native label kept in metadata.
- **Uncertainty rebuild** — if `CR.metadata` counts are missing (e.g. a hand-posted
  reasoning object), all uncertainty strings default to the `low` bucket, so the
  decision will not see them as high-severity blockers. Safe by design: never *invents*
  high-severity signals; faithful whenever the reasoning came through our adapter.
- **`interview_focus` / `recommendations` are derived**, not produced by Developer 4's
  `DecisionEngine` (which has no such outputs). Grounded in real gaps; clearly synthesized.

---

## 6. Summary of intentional losses

| Theme | Where | Recovered when |
|---|---|---|
| Entity resolution / canonical ids | EvidenceProviderAdapter | Graph Intelligence (entity_resolver) |
| Graph structure (nodes/edges/fusion) | NoOpGraphAdapter / NoOpFusionEngine | Graph Intelligence (GraphBuilder/FusionEngine) |
| Themed / cross-entity claims | ReasoningEngineAdapter (graph-disabled) | Graph present → native ClaimSynthesizer |
| Uncertainty per-item detail | ReasoningEngineAdapter | n/a (not on shared contract; counts retained) |
| 6→5 recommendation labels | DecisionEngineAdapter | n/a (native label kept in metadata) |

All losses are either (a) inherent to Graph Intelligence being absent and recovered when
it lands through the same DI slots, or (b) reductions to fields outside the shared
contract, with the signal preserved in `metadata`. No adapter invents facts.
