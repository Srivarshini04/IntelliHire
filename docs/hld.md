# DELULU — High-Level Design

## Mission

Discover high-potential candidates overlooked by traditional ATS systems through evidence-driven, explainable hiring intelligence.

**Tagline:** We don't rank resumes. We rank evidence.

## MVP Goal

```
JD → Candidate Profiles → Ranking → Hidden Talent Discovery → Explanation
```

## Architecture (Modular Monolith)

```
Recruiter
    ↓
DELULU Dashboard (Next.js)
    ↓
FastAPI Backend
    ├── Job Intelligence Engine
    ├── Evidence Collection Engine
    ├── Relevance Filter Engine
    ├── Capability Engine
    ├── Risk Engine
    ├── Hidden Talent Engine
    ├── Ranking Engine
    └── Explainability Engine
    ↓
PostgreSQL | Qdrant | Redis
```

## Core Domain Objects

| Object | Purpose |
|--------|---------|
| Role Blueprint | Generated from JD — skills, traits, weights |
| Candidate Profile | Resume + LinkedIn + GitHub evidence |
| Capability Profile | Technical, execution, ownership, learning scores |
| Risk Profile | Evidence, role gap, credibility risks |
| Hidden Talent Profile | Visibility vs capability (HTI) |
| Final Recommendation | Fit score, confidence, recommendation |

## Technology Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 16, TypeScript, Tailwind, shadcn/ui, Recharts |
| Backend | FastAPI, Python, Celery, Redis |
| AI | Gemini, Sentence Transformers, BGE Embeddings |
| Storage | PostgreSQL, Qdrant, Redis |

## Out of Scope (MVP)

Neo4j, Multi-Agent Debate, Digital Twin, ATS Integrations, Continuous Learning, Enterprise Connectors

## Demo Flow

1. Upload JD
2. Upload 20 candidates
3. DELULU analyzes evidence
4. Creates capability profiles
5. Computes risk + HTI
6. Ranks candidates
7. Explains ranking
8. Surfaces hidden talent

See the full vision document: `DELULU Final Vision HLD.docx`
