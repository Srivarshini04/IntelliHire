# DELULU v2 — Branch Strategy

A lightweight model for a **4-developer hackathon**, organized around one shared
foundation branch and one feature branch per workstream.

## Branch topology

```
main
 └── feat/delulu-v2-foundation          ← base branch; holds the frozen app.shared contracts
      ├── feat/v2-persistence           ← Workstream: repositories / DB / persistence
      ├── feat/v2-api                    ← Workstream: FastAPI v2 endpoints + request schemas
      ├── feat/v2-mock-data             ← Workstream: mock fixtures, sample candidates, seeds
      └── feat/v2-docs                  ← Workstream: documentation (this folder)
```

- **`feat/delulu-v2-foundation`** is the integration base. It contains
  `app.shared` (models, enums, interfaces, context, constants) — the frozen
  contracts every workstream consumes.
- Each workstream gets **exactly one feature branch** cut off the foundation branch.
- **PRs target `feat/delulu-v2-foundation`** (not `main`). `main` only receives the
  foundation branch once the integration is green.
- Treat any change to `app.shared` as a **protocol change**: announce it, land it on
  the foundation branch first, then rebase the workstream branches.

## Commit format

```
type(scope): subject
```

- `type` ∈ `feat | fix | docs | refactor | test | chore`.
- `scope` is the area touched, e.g. `shared`, `api`, `ranking`, `persistence`,
  `docs`, `mock`.
- Examples:
  - `feat(api): add POST /v2/ranking/rank route`
  - `docs(architecture): document decisions A/B/C`
  - `fix(ranking): keep score non-increasing by rank`

## Merge strategy

**Squash-merge** every PR into `feat/delulu-v2-foundation` — one tidy commit per PR
keeps the foundation history linear and easy to bisect. The squash commit message
uses the `type(scope): subject` format above.

## PR template

```markdown
## Workstream
<!-- persistence | api | mock-data | docs -->

## What & why
<!-- 1–3 sentences. Link the issue/task. -->

## Shared contracts touched
<!-- List any app.shared changes, or "none". Any change here is a protocol change. -->

## Checklist
- [ ] Targets `feat/delulu-v2-foundation`
- [ ] Imports contracts from `app.shared` (no local redefinitions)
- [ ] Stage impls match the Protocol signatures in app.shared.interfaces.pipeline
- [ ] Imports cleanly under the repo-root `.venv`
- [ ] Submission output (if any) passes validate_submission.py
- [ ] Squash-merge ready (clean title in `type(scope): subject`)
```

## Ownership matrix — shared contract → consuming workstream(s)

Which workstreams **consume** (import) each frozen contract. `feat/v2-foundation`
**owns** all of `app.shared`; no other workstream edits it.

| Shared contract (`app.shared`) | persistence | api | mock-data | docs |
|--------------------------------|:-----------:|:---:|:---------:|:----:|
| `models.Evidence` / `EvidenceLedgerEntry` | ✅ | ✅ | ✅ | ✅ |
| `models.CandidateGraph` (`GraphNode`, `GraphEdge`) | ✅ | ✅ | ✅ | ✅ |
| `models.RoleDNA` | ✅ | ✅ | ✅ | ✅ |
| `models.CandidateReasoning` (`ReasoningClaim`, `CandidateGap`) | ✅ | ✅ | — | ✅ |
| `models.HiringDecision` (`Recommendation`, `InterviewFocus`) | ✅ | ✅ | — | ✅ |
| `models.CandidateRanking` / `RankedList` | ✅ | ✅ | ✅ | ✅ |
| `enums.*` (`EvidenceSource`, `EvidencePolarity`, `EvidenceType`, `GraphNodeType`/`EdgeType`, `Intensity`, `RankingStage`, `GapSeverity`, `RecommendationLevel`/`Action`, `VerificationStatus`) | ✅ | ✅ | ✅ | ✅ |
| `interfaces.*` (`EvidenceProvider` … `RankingEngine`, `RoleDNAProvider`) | — | ✅ | — | ✅ |
| `context.PipelineContext` | ✅ | ✅ | — | ✅ |
| `constants.*` (`SOURCE_WEIGHTS`, `DEFAULT_RETRIEVAL_TOP_K`, `SUBMISSION_SIZE`, thresholds) | ✅ | ✅ | ✅ | ✅ |

Legend: ✅ = consumes/imports · — = not directly consumed.
