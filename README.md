# DELULU — AI Hiring Intelligence Platform

> **We don't rank resumes. We rank evidence.**

DELULU discovers high-potential candidates overlooked by traditional ATS systems through evidence-driven, explainable hiring intelligence.

## Mission

Find capable candidates—not just visible ones—by analyzing resume, GitHub, LinkedIn, and portfolio evidence against a role-specific blueprint.

## Monorepo Structure

```
IntelliHire/
├── frontend/          # Next.js dashboard (Member 3)
├── backend/           # FastAPI modular monolith (Members 1 & 2)
├── shared/            # Schemas, prompts, API contracts
├── docs/              # HLD, LLD, scoring, architecture
├── datasets/          # Demo dataset & ATS baseline (Member 4)
├── scripts/           # Dev & seed scripts
├── docker/            # Docker configs
└── docker-compose.yml
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 20+
- Python 3.10+

### 1. Start infrastructure

```bash
docker compose up -d postgres redis qdrant
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Dashboard: http://localhost:3000

## MVP Workflow

```
Upload JD → Create Role Blueprint → Upload Candidates → Analyze Evidence
    → Capability + Risk + HTI Scores → Rank → Explain
```

## Team Ownership

| Member | Role | Modules | Branches |
|--------|------|---------|----------|
| **1** | AI Core Lead | JD Parser, Capability, Risk, HTI, Ranking | `feat/job-intelligence`, `feat/scoring-engine`, `feat/ranking` |
| **2** | Data Ingestion Lead | Resume/GitHub/LinkedIn parsers, Evidence Store | `feat/evidence`, `feat/github-parser`, `feat/resume-parser` |
| **3** | Frontend Lead | Dashboard, Rankings, Candidate Detail, Charts | `feat/frontend`, `feat/dashboard` |
| **4** | Evaluation & Demo Lead | Dataset, ATS baseline, Metrics, Pitch | `feat/evaluation`, `feat/demo` |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/jobs` | Create job from JD |
| `POST` | `/api/candidates` | Upload candidate |
| `POST` | `/api/candidates/{id}/analyze` | Run analysis pipeline |
| `GET` | `/api/jobs/{job_id}/rankings` | Get ranked candidates |
| `GET` | `/api/candidates/{id}` | Candidate detail + explanation |

See [docs/api-contracts.md](docs/api-contracts.md) for full contracts.

## Scoring Formula

```
Capability = 0.30×Technical + 0.30×Execution + 0.20×Ownership + 0.20×Learning
HTI        = Capability − Visibility (normalized 0–100)
Fit Score  = 0.55×Capability + 0.25×HTI + 0.20×Confidence − 0.15×Risk
```

## Demo Dataset Strategy

Create **20 candidates** for one role (AI Engineer):

- **Group A** (5): Obvious strong — MIT/Google/OpenAI credentials
- **Group B** (10): Average candidates
- **Group C** (5): Hidden talent — unknown college, strong GitHub/projects

Target demo moment: ATS ranks hidden talent #15, DELULU ranks them #2.

## Docs

- [HLD](docs/hld.md) — High-level design
- [LLD](docs/lld.md) — Low-level design & module specs
- [Scoring](docs/scoring.md) — Engine formulas
- [API Contracts](docs/api-contracts.md) — Request/response schemas

## License

Hackathon project — internal use.
