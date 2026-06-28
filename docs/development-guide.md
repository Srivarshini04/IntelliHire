# DELULU v2 — Development Guide

## Coding standards

- **Python + Pydantic v2.** All domain models are `pydantic.BaseModel` subclasses
  with `Field(...)` metadata. Use v2 idioms (`model_validator(mode="after")`,
  `model_dump`, `Field(default_factory=...)`).
- **`from __future__ import annotations`** at the top of *every* module. All shared
  contracts already do this; new modules must too.
- **Full typing, always.** Annotate every parameter and return type. Prefer modern
  syntax: `list[Evidence]`, `str | None`, `dict[str, Any]`. Use `Literal[...]` for
  fixed values (e.g. `schema_version: Literal["1.0"]`).
- **Async signatures.** Every pipeline stage method is `async` so the orchestrator
  can `await` uniformly — even pure-compute implementations (see the Protocols in
  `app.shared.interfaces.pipeline`). Match those signatures exactly.
- **String-valued enums.** All `app.shared.enums` members are `(str, Enum)` so they
  serialize cleanly to JSON / JSONB and round-trip through the API and DB.
- **Confidence is always `0.0..1.0`** (`Field(ge=0.0, le=1.0)`); bands come from
  `ConfidenceLevel` / the thresholds in `app.shared.constants`.

## Naming conventions

- **Modules/packages:** `snake_case` (`confidence_fusion.py`, `pipeline_context.py`).
- **Classes / models / Protocols:** `PascalCase` (`Evidence`, `RoleDNAProvider`).
- **Stable ids** follow `prefix:scope` patterns used in the contracts:
  `ev_github_0001` (evidence), `skill:fastapi` (entity / node), `graph:c1:j1`,
  `roledna:j1`, `reasoning:c1:j1`, `decision:c1:j1`, `ranking:j1:c1`,
  `rankedlist:j1:rerank`. Server assigns these — request models omit them.
- **Canonical entity refs** are produced by `entity_resolver` (e.g.
  `SKILL_*`, `ORG::*`, `skill:fastapi`) and are the fusion/dedup key.

## Importing shared contracts

Always import from `app.shared` — never re-declare a contract:

```python
from app.shared.models import Evidence, CandidateGraph, RoleDNA, HiringDecision
from app.shared.interfaces import EvidenceProvider, ReasoningEngine, RankingEngine
from app.shared.enums import EvidencePolarity, EvidenceSource, Intensity, RankingStage
from app.shared.constants import SOURCE_WEIGHTS, DEFAULT_RETRIEVAL_TOP_K, SUBMISSION_SIZE
from app.shared.context import PipelineContext
```

## The golden rule — never redefine a shared contract

> There is exactly one definition of each contract in the repository.
> **Compose or subclass; never redefine.**

- Need extra fields for a request? Build a *new* request model that **embeds** the
  shared model (e.g. `app.api.v2.schemas.ExtractEvidenceResponse` holds
  `evidence: list[Evidence]`). Request models also **omit server-generated ids**.
- Need richer behaviour? Subclass or wrap, don't fork the type.
- Legacy types (`graph_schema.UnifiedCandidateGraph`, the old
  `EvidenceLedgerEntry`) now **re-export** the shared definitions — follow that
  pattern rather than copying fields.
- Editing anything in `app.shared` is a **breaking change** for all four
  workstreams: announce it before merging.

## Run & verify (repo-root `.venv`)

The virtualenv lives at the **repository root** (`/.venv`), not under `backend/`.

```bash
# from the repo root
source .venv/bin/activate

# import-check the frozen contracts
python -c "from app.shared.models import Evidence, CandidateGraph, RoleDNA, HiringDecision; print('shared ok')"
python -c "from app.shared.interfaces import EvidenceProvider, RankingEngine; print('interfaces ok')"

# run the API
uvicorn main:app --reload          # or: python main.py

# validate a challenge submission CSV (exactly 100 rows)
python "challenge_data/[PUB] India_runs_data_and_ai_challenge/India_runs_data_and_ai_challenge/validate_submission.py" team_xxx.csv
```

Verification checklist before opening a PR:

1. Module imports cleanly under the root `.venv`.
2. New code imports contracts from `app.shared` (no local redefinitions).
3. Stage implementations match the `Protocol` signature in
   `app.shared.interfaces.pipeline` (names, `async`, types).
4. Any submission output passes `validate_submission.py`.
