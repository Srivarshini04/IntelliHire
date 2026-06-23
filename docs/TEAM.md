# Team Guide

## Branch Strategy

Each member works on feature branches, then opens PRs to `main`.

| Member | Role | Branches |
|--------|------|----------|
| 1 — AI Core | JD parser, capability, risk, HTI, ranking engines | `feat/job-intelligence`, `feat/scoring-engine`, `feat/ranking` |
| 2 — Data Ingestion | Resume/GitHub/LinkedIn parsers, evidence store | `feat/evidence`, `feat/github-parser`, `feat/resume-parser` |
| 3 — Frontend | Dashboard, rankings, candidate detail, charts | `feat/frontend`, `feat/dashboard` |
| 4 — Evaluation | Dataset, ATS baseline, metrics, pitch deck | `feat/evaluation`, `feat/demo` |

## Getting Started

```bash
# Clone and setup
git clone https://github.com/Venuenugula/IntelliHire.git
cd IntelliHire
chmod +x scripts/dev.sh
./scripts/dev.sh

# Backend (terminal 1)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload

# Frontend (terminal 2)
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## Code Conventions

- Backend: async FastAPI, SQLAlchemy 2.0, Pydantic v2
- Frontend: Next.js App Router, TypeScript, Tailwind
- Shared schemas live in `shared/` — update both backend and frontend when changing contracts
- API contracts documented in `docs/api-contracts.md`

## PR Checklist

- [ ] Works locally with docker compose up
- [ ] No secrets committed (.env files are gitignored)
- [ ] API changes reflected in `docs/api-contracts.md`
- [ ] Feature branch rebased on latest `main`
