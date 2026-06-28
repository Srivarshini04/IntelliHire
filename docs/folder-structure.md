# DELULU v2 — Folder Structure

The backend lives under `backend/app/`. The contract layer (`shared/`) is the single
source of truth; everything else depends on it, never the reverse.

```
backend/app/
├── shared/             # ★ FROZEN v2 contracts — single source of truth
│   ├── models/         #   domain models: Evidence, CandidateGraph, RoleDNA,
│   │                   #   CandidateReasoning, HiringDecision, CandidateRanking/RankedList
│   ├── enums/          #   controlled vocabularies (EvidenceSource, EvidencePolarity,
│   │                   #   EvidenceType, GraphNodeType/EdgeType, Intensity, RankingStage, ...)
│   ├── interfaces/     #   pipeline Protocols (EvidenceProvider ... RankingEngine)
│   ├── context/        #   PipelineContext — per-(candidate, job) carrier object
│   └── constants/      #   cross-cutting tunables: SOURCE_WEIGHTS, TOP_K, SUBMISSION_SIZE
│
├── api/                # FastAPI routers
│   └── v2/             #   v2 endpoints (prefix /v2): schemas.py (request models) + routes/
├── intelligence/       # pipeline brains / orchestration
│   ├── candidate_graph/#   confidence_fusion (probability-of-support), entity_resolver, graph_schema
│   ├── jd/             #   job-description understanding
│   └── resume/         #   resume understanding
├── services/           # business-logic services per concern
│   ├── evidence/       #   evidence assembly services
│   ├── ranking/        #   ranking services (two-stage funnel support)
│   ├── capability/     #   capability scoring
│   ├── confidence/     #   confidence services
│   ├── hti/            #   hireability / talent-index services
│   ├── jd/             #   JD services
│   └── risk/           #   risk / red-flag services
├── knowledge/          # canonical knowledge base: skill normalizer, loader, data/
├── documents/          # document ingestion: artifacts, chunker, PII, quality, storage
├── models/             # legacy / persistence-side data models (candidate, job, evidence, ledger, scoring)
├── schemas/            # Pydantic API schemas + reused primitives (fields: ConfidenceLevel, SourceSpan)
├── pipeline/           # v1 analysis pipeline stages (capabilities, evidence_graph, explainability, ...)
├── llm/                # LLM provider abstraction (factory, gemini, base)
├── core/               # config, database, security, app wiring
├── github_intel/       # GitHub intelligence (models, database, seed)
├── skills/             # skill matching + normalizer helpers
├── mock/               # mock data fixtures (mock_candidate.json)
└── workers/            # background workers
```

> A `repositories/` directory (persistence layer) is planned for the
> `feat/v2-persistence` workstream and is not yet present.

**Dependency direction.** `intelligence`, `services`, `api`, `documents`, and
`mock` all import their contracts from `app.shared`. `app.shared` imports from
nothing else in the app except the small reused primitives in `app.schemas.fields`
(`ConfidenceLevel`, `SourceSpan`). This keeps `shared` a leaf the whole system can
depend on safely.
