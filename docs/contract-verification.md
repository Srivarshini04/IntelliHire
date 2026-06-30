# DELULU v2 — Phase 2 Contract Verification

**Branch:** `develop` @ `721784c`
**Principle:** `app/shared` is the single source of truth. Mismatches are bridged with
adapters in `app/runtime/adapters/` — never by rewriting implementations or redefining
contracts.

---

## 1. Method

For every module on the v2 path we verified that domain types, enums, interfaces,
context, and constants come from `app/shared`, and that each completed engine either
*conforms to* its shared `Protocol` or is *bridged by an adapter*. Conformance was
proven at runtime via `isinstance(adapter, <Protocol>)` against the
`@runtime_checkable` interfaces, plus an end-to-end conversion run.

---

## 2. Shared-contract usage (v2 modules)

| Module | Imports from `app/shared` | Verdict |
|---|---|---|
| `runtime/candidate_evaluation_pipeline.py` | models, interfaces, context | ✅ conforms |
| `runtime/ranking_orchestrator.py` | models, interfaces, constants | ✅ conforms |
| `runtime/pipeline_runtime.py`, `stage.py`, `stages.py` | interfaces, context | ✅ conforms |
| `runtime/deterministic_ranking_engine.py` | models, enums, constants | ✅ conforms |
| `runtime/deps.py` | interfaces | ✅ conforms (extended in Phase 3) |
| `intelligence/role_dna/role_dna_provider.py` | models, enums | ✅ conforms (already wired) |
| `intelligence/reasoning/*` | models (`ReasoningClaim`), enums | ⚠️ engine signature mismatch → adapter |
| `intelligence/decision/decision_engine.py` | models (`ReasoningClaim`), enums | ⚠️ engine signature mismatch → adapter |
| `services/evidence/*` (Developer 2) | **none** (own `EvidenceObject`, `source: str`) | ⚠️ model mismatch → adapter |
| `api/v2/routes/*`, `api/v2/schemas.py` | models, enums, interfaces, constants | ✅ conforms |

**No module redefines a shared contract.** The 18 duplicate class names from Phase 1
are ORM-vs-contract layer separation or interface-vs-implementation pairs (see audit
§3); none is a competing definition of a shared model/enum/interface.

---

## 3. Mismatches and their adapter resolution

| Shared contract (async) | Implementation | Mismatch | Adapter |
|---|---|---|---|
| `EvidenceProvider.collect(candidate_id, raw) -> list[Evidence]`, `source: EvidenceSource` | Dev 2 `normalize(source, pkg) -> EvidenceObject`; `source: str` | model + signature + enum | **`EvidenceProviderAdapter`** |
| `GraphBuilder.build(...) -> CandidateGraph` | **absent** (Developer 3) | not implemented | **`NoOpGraphAdapter`** (passthrough + telemetry) |
| `FusionEngine.fuse(graph) -> CandidateGraph` | **absent** (Developer 3) | not implemented | **`NoOpFusionEngine`** (graph-disabled no-op) |
| `ReasoningEngine.reason(graph, role) -> CandidateReasoning` | Dev 4 **sync** `reason(graph, role) -> ReasoningResult` | sync→async + return type | **`ReasoningEngineAdapter`** |
| `DecisionEngine.decide(reasoning, role) -> HiringDecision` | Dev 4 **sync** `decide(result) -> DecisionResult`; own `Recommendation` enum | sync→async + input + return + enum | **`DecisionEngineAdapter`** |

### Conversion details (all confined to the adapters)
- **Evidence:** `EvidenceObject` → atomic `Evidence` (one `SKILL` per detected skill +
  one `ASSESSMENT` summary). Confidence from `relevance_score` (0..100) or `reliability`
  (0..1). Failed/empty source → `[]` (DECISION C: absence is never Evidence).
- **Reasoning:** native `ReasoningResult` → `CandidateReasoning`; `GapAnalysis` →
  `list[CandidateGap]` with `GapSeverity` (`critical→BLOCKING`, `moderate→MODERATE`,
  `minor→MINOR`); severity-bucket counts + strengths stamped into `metadata` so the
  decision adapter can reconstruct faithfully.
- **Decision:** `CandidateReasoning` → reconstructed `ReasoningResult` (gaps round-trip
  exactly; uncertainties bucketed from stamped counts, else safely to `low`) → native
  `decide()` → `HiringDecision`; native `Recommendation` → `RecommendationLevel`
  (`interview*→LEAN_HIRE`, `needs_more_information→INSUFFICIENT_EVIDENCE`,
  `reject→NO_HIRE`).

---

## 4. The `NoOpFusionEngine` addition (flagged)

The directive names four adapters. A fifth tiny class, **`NoOpFusionEngine`**, was added
**only** because the frozen `CandidateEvaluationPipeline` (Developer 1) runs a
`FusionStage`, and fusion is part of Developer 3's absent graph intelligence. Rather than
modify Developer 1's pipeline to drop the stage, we inject a no-op fusion (returns the
graph unchanged) via DI in Phase 3. It lives in `noop_graph_adapter.py` so all
graph-disabled behaviour is in one place. This honors *both* "do not rewrite another
developer's module" and "do not fake graph reasoning."

---

## 5. Verification performed

```
isinstance checks (runtime_checkable Protocols):
  EvidenceProvider: True   GraphBuilder: True   FusionEngine: True
  ReasoningEngine : True   DecisionEngine: True

End-to-end conversion run:
  GitHub pkg -> 3 Evidence (2 skill + 1 assessment); failed source -> 0 Evidence
  NoOpGraphAdapter -> empty graph (nodes=0, ledger=0) + {graph_stage: skipped, evidence_count: 3}
  ReasoningEngineAdapter (empty graph) -> 0 claims, 2 blocking gaps, confidence 0.26
  DecisionEngineAdapter -> no_hire, derived_score 0.0, full reasons/reservations/focus

Regression:
  293/293 tests pass · app imports · OpenAPI builds (24 paths)
```

---

## 6. Known limitation surfaced (carried to Phase 8)

With `NoOpGraphAdapter`, the `ReasoningEngine` receives an **empty graph** (no nodes),
so — per Developer 4's design (`ClaimSynthesizer` returns `[]` when `graph.nodes` is
empty) — it produces **no claims** and the `DecisionEngine` returns conservative
`no_hire` / `insufficient_evidence`. The pipeline executes end-to-end and degrades
gracefully; rich reasoning output requires the real Candidate Graph. This is the correct,
honest behaviour given Graph Intelligence is intentionally absent — not a wiring defect.

---

## 7. Verdict

**PASS.** `app/shared` is the sole source of truth; no contract was redefined; every
mismatch is resolved inside the new anti-corruption layer at `app/runtime/adapters/`.
Implementations remain untouched. Ready for Phase 3 (dependency injection).
