# Team Guide

## Document Intelligence Platform (new)

See [document-intelligence.md](./document-intelligence.md) for full architecture.

**Foundation branch:** `feat/document-understanding-engines`

| Member | Role | Branches |
|--------|------|----------|
| 1 — JD Intelligence | Document layer, JD upload, Blueprint generator | `feat/jd-intelligence` |
| 2 — Resume Intelligence | Resume upload, CandidateProfile, validation | `feat/resume-intelligence` |
| 3 — Frontend | Review UI (edit blueprint/profile before save) | `feat/frontend`, `feat/document-review-ui` |
| 4 — Evaluation | Dataset, ATS baseline, metrics, pitch | `feat/evaluation`, `feat/demo` |
| Integration | GitHub, LinkedIn, LeetCode, Capability engine | `main` + evidence branches |

## Branch Strategy

Each member works on feature branches, then opens PRs to `main`.

Legacy branches (pre-document-intelligence):

| Member | Role | Branches |
|--------|------|----------|
| 1 — AI Core | Capability, risk, HTI, ranking engines | `feat/scoring-engine`, `feat/ranking` |
| 2 — Data Ingestion | GitHub/LinkedIn evidence (done on main) | `feat/evidence` |
| 3 — Frontend | Dashboard, rankings, candidate detail | `feat/dashboard` |

## Getting Started

```bash
git clone https://github.com/Venuenugula/IntelliHire.git
cd IntelliHire
git checkout feat/document-understanding-engines  # architecture branch
chmod +x scripts/dev.sh && ./scripts/dev.sh

cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
uvicorn app.main:app --reload
```

## Code Conventions

- **Document, not string** — engines consume `Document`, never raw text
- **LLM abstraction** — call `get_llm_provider().generate_json()`, never Gemini directly
- **Confidence everywhere** — use `ExtractedField` / `SkillField` with `value`, `confidence`, `source`
- **Review before save** — upload endpoints return drafts; persist only on approve
- Shared schemas: `shared/role_blueprint.json`, `backend/app/schemas/`

## PR Checklist

- [ ] Works locally with docker compose up
- [ ] No secrets committed
- [ ] API changes in `docs/api-contracts.md`
- [ ] Versioning metadata on blueprints/profiles
- [ ] SkillNormalizer applied before blueprint generation
