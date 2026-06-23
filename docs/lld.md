# DELULU — Low-Level Design

## Folder Structure

```
backend/app/
├── api/          jobs.py, candidates.py, rankings.py, analysis.py
├── core/         config.py, database.py, security.py
├── models/       job, candidate, evidence, scoring
├── schemas/      Pydantic request/response models
├── services/
│   ├── jd/           JD parser
│   ├── evidence/     Resume, GitHub, LinkedIn parsers + relevance
│   ├── capability/   Capability engine
│   ├── risk/         Risk engine
│   ├── hti/          Hidden Talent Index engine
│   └── ranking/      Ranking + explainability
└── workers/      Celery background jobs
```

## Core Workflow

```
Create Job → Parse JD → Generate Role Blueprint
    → Upload Candidates → Collect Evidence
    → Relevance Filtering → Signal Extraction
    → Capability Score → Risk Score → HTI Score
    → Ranking → Explanation
```

## Database Tables

- `jobs` — id, title, description, role_blueprint (JSONB)
- `candidates` — id, job_id, name, email, urls, resume_path
- `candidate_evidence` — id, candidate_id, source_type, raw/processed content
- `capability_profiles` — technical, execution, ownership, learning_velocity, capability_score
- `risk_profiles` — evidence_risk, role_gap_risk, credibility_risk, risk_score
- `hidden_talent_profiles` — visibility_score, hti_score
- `rankings` — job_id, candidate_id, fit_score, confidence, rank, recommendation

## Module APIs

### Job Intelligence
- `POST /api/jobs` — Create job, parse JD, return role blueprint

### Candidate Evidence
- `POST /api/candidates` — Upload candidate with resume/GitHub/LinkedIn
- `POST /api/candidates/{id}/analyze` — Run analysis pipeline

### Rankings
- `GET /api/jobs/{job_id}/rankings` — Ranked candidate list
- `GET /api/candidates/{id}` — Full detail with explanation

### Batch Analysis
- `POST /api/analysis/jobs/{job_id}/run` — Analyze all candidates for a job

## Frontend Pages

| Page | Route | Purpose |
|------|-------|---------|
| Job Upload | `/jobs/new` | Paste JD, create job |
| Candidate Upload | `/jobs/[id]/candidates` | Upload resumes + links |
| Rankings | `/jobs/[id]/rankings` | Ranked table with scores |
| Candidate Detail | `/candidates/[id]` | Radar chart, risk, explanation |
