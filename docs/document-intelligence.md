# Document Intelligence Platform — Architecture

> **DELULU does not build parsers. It builds a Document Intelligence Platform.**
>
> Every downstream engine (Capability, Risk, HTI, Ranking) depends on structured, confident, versioned outputs from this layer.

**Branch:** `feat/document-understanding-engines`  
**Status:** Approved architecture — implementation pending  
**Approved:** Gemini via abstract `LLMProvider`, Option B APIs, full schema, review-before-save

---

## Design principles

1. **Document, not string** — all engines consume a `Document` domain model, never raw text.
2. **Confidence everywhere** — every extracted field carries `value`, `confidence`, `source`.
3. **Review before persist** — recruiter edits JD blueprint and resume profile before save; edits are training data.
4. **Version everything** — blueprint, parser, prompt, and model versions stored on every artifact.
5. **Audit trail** — original file → extracted text → cleaned text → AI output → human edits → final.
6. **Provider abstraction** — business logic calls `llm.generate_json()` only; never Gemini/OpenAI directly.
7. **Skill normalization** — `SkillNormalizer` deduplicates variants before blueprint generation and ranking.

---

## End-to-end pipeline

```text
Document Upload
        │
        ▼
Document Understanding Layer          ← shared foundation
  extractor · cleaner · chunker
  metadata · language_detector · pii
        │
        ▼
Document (domain model)
        │
        ├────────────────────┬────────────────────┐
        ▼                    ▼                    ▼
   JD Intelligence      Resume Intelligence   (future parsers)
        │                    │
        ▼                    ▼
   RoleBlueprint       CandidateProfile
   (review → edit)      (review → edit)
        │                    │
        └──────────┬─────────┘
                   ▼
          Evidence Aggregator
     (GitHub · LinkedIn · LeetCode)
                   ▼
          Capability Engine
                   ▼
             Risk Engine
                   ▼
             HTI Engine
                   ▼
           Ranking Engine
                   ▼
    Recommendation + Explainability
```

---

## Layer 1: Document Understanding (shared)

**Owner:** Member 1 (foundation) + Member 2 (consumers)

```
backend/app/documents/
├── extractor.py          # PDF (PyMuPDF) + DOCX (python-docx)
├── cleaner.py            # whitespace, symbols, line breaks
├── chunker.py            # section-aware chunks for LLM context
├── metadata.py           # pages, filetype, size, hash
├── language_detector.py  # document language
├── pii.py                # optional PII redaction flags
└── service.py            # orchestrates → Document
```

**Output:** `Document` (see `backend/app/schemas/document.py`)

Future parsers reuse this layer:
- Cover Letter, Portfolio, Offer Letter, Performance Review, Research Paper

---

## Layer 2: Intelligence engines

### JD Intelligence (Member 1)

```
backend/app/intelligence/jd/
├── blueprint_generator.py   # Document → RoleBlueprint via LLM
└── prompts/                 # versioned prompt templates
```

### Resume Intelligence (Member 2)

```
backend/app/intelligence/resume/
├── profile_extractor.py     # Document → CandidateProfile via LLM
├── profile_validator.py     # schema + confidence thresholds
└── prompts/
```

### Skills (shared)

```
backend/app/skills/
└── normalizer.py            # Tensor Flow / TensorFlow / TF → TensorFlow
```

---

## Layer 3: LLM abstraction

```
backend/app/llm/
├── base.py          # LLMProvider protocol
├── gemini.py        # default provider
├── openai.py        # stub — swap without touching engines
├── factory.py       # LLM_PROVIDER env → provider instance
└── types.py         # GenerateJsonRequest / Response
```

**Rule:** engines call only:

```python
result = await llm.generate_json(prompt=..., schema=RoleBlueprint, ...)
```

---

## Domain models

### Document

```python
class Document(BaseModel):
    filename: str
    filetype: str              # pdf | docx
    pages: int
    language: str
    raw_text: str
    cleaned_text: str
    sections: dict[str, str]   # e.g. {"requirements": "...", "responsibilities": "..."}
    metadata: dict
    confidence: float          # extraction quality 0–1
```

### ExtractedField (confidence + explainability)

```python
class ExtractedField(BaseModel, Generic[T]):
    value: T
    confidence: float          # 0.0 – 1.0
    source: str | None = None  # verbatim quote from document
```

### RoleBlueprint (full schema — single source of truth)

| Field | Type | Notes |
|-------|------|-------|
| `role_title` | `ExtractedField[str]` | |
| `experience_level` | `ExtractedField[str]` | junior \| mid \| senior \| lead |
| `required_skills` | `list[SkillField]` | normalized + confidence |
| `preferred_skills` | `list[SkillField]` | |
| `responsibilities` | `list[ExtractedField[str]]` | |
| `behavioral_traits` | `list[ExtractedField[str]]` | |
| `education` | `list[ExtractedField[str]]` | |
| `certifications` | `list[ExtractedField[str]]` | |
| `domain` | `ExtractedField[str]` | e.g. fintech, healthcare |
| `industry` | `ExtractedField[str]` | |
| `tools` | `list[SkillField]` | |
| `success_metrics` | `list[ExtractedField[str]]` | |
| `capability_weights` | `dict[str, float]` | sum = 1.0 |
| `required_evidence` | `list[str]` | for evidence pipeline |
| `versioning` | `BlueprintVersioning` | see below |

### BlueprintVersioning

```json
{
  "blueprint_version": "1.0.0",
  "parser_version": "1.0.0",
  "prompt_version": "1.0.0",
  "llm_model": "gemini-2.0-flash",
  "generated_at": "2026-06-23T12:00:00Z"
}
```

### CandidateProfile (Member 2)

| Field | Type |
|-------|------|
| `name` | `ExtractedField[str]` |
| `email` | `ExtractedField[str]` |
| `phone` | `ExtractedField[str]` |
| `skills` | `list[SkillField]` |
| `experience` | `list[ExperienceEntry]` |
| `projects` | `list[ProjectEntry]` |
| `education` | `list[EducationEntry]` |
| `certifications` | `list[ExtractedField[str]]` |
| `github_url` | `ExtractedField[str]` |
| `linkedin_url` | `ExtractedField[str]` |
| `leetcode_url` | `ExtractedField[str]` |
| `portfolio_url` | `ExtractedField[str]` |
| `versioning` | `ProfileVersioning` |

---

## API design (Option B)

### Granular — independently testable

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/jobs/upload` | PDF/DOCX → `Document` + cleaned text |
| `POST` | `/api/jobs/blueprint` | text or `document_id` → `RoleBlueprint` (draft) |
| `POST` | `/api/candidates/upload` | PDF/DOCX → `CandidateProfile` (draft) |

### Workflow — compose engines

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/jobs` | Approve + save job with final blueprint |
| `POST` | `/api/candidates` | Approve + save candidate with final profile |
| `POST` | `/api/jobs/analyze` | *(future)* upload → parse → blueprint → save in one call |

### Recruiter flow (JD)

```
Upload JD (POST /jobs/upload)
    → AI extracted text + Document
    → Generated Blueprint (POST /jobs/blueprint)
    → Recruiter reviews/edits in UI
    → Approve (POST /jobs with edited blueprint)
    → Saved to jobs.role_blueprint
```

### Recruiter flow (Resume)

```
Upload Resume (POST /candidates/upload)
    → CandidateProfile draft
    → Recruiter reviews/edits
    → Approve (POST /candidates with profile + job_id)
    → URLs auto-wired to evidence pipeline
```

---

## Artifact storage (audit trail)

Persist every stage — do not discard.

```
backend/uploads/documents/
  {document_id}/
    original.pdf
    extracted.json       # Document model
    blueprint_draft.json
    blueprint_edited.json
    blueprint_final.json
```

**DB table (planned):** `document_artifacts`

| Column | Purpose |
|--------|---------|
| `id` | UUID |
| `entity_type` | job \| candidate |
| `entity_id` | FK after save |
| `stage` | original \| extracted \| cleaned \| blueprint_draft \| blueprint_edited \| blueprint_final |
| `content` | JSONB |
| `versioning` | JSONB |
| `created_at` | timestamp |

Recruiter edits stored as `blueprint_edited` — valuable for future fine-tuning.

---

## LLM provider decision

**Default: Gemini**

| Reason | |
|--------|--|
| Already integrated | ✓ |
| Lower latency / cost | ✓ |
| Larger context | ✓ |
| No migration | ✓ |

Configurable via `LLM_PROVIDER=gemini|openai|claude` in `.env`.

---

## Team ownership

| Member | Owns |
|--------|------|
| **Member 1** | Document layer foundation, JD upload, Blueprint generator |
| **Member 2** | Resume upload, CandidateProfile extractor, Profile validator |
| **Integration** | GitHub, LinkedIn, LeetCode, Evidence, Capability engine |

**Branches:**
- `feat/document-understanding-engines` — shared architecture (this branch)
- `feat/jd-intelligence` — Member 1 implementation
- `feat/resume-intelligence` — Member 2 implementation

---

## Implementation phases

| Phase | Deliverable | Owner |
|-------|-------------|-------|
| **0** | Architecture + schemas + LLM abstraction + stubs | Done on this branch |
| **1** | `Document` extraction (PDF/DOCX) + `POST /jobs/upload` | Member 1 |
| **2** | Blueprint generator + `POST /jobs/blueprint` + skill normalizer | Member 1 |
| **3** | Resume extractor + `POST /candidates/upload` + validator | Member 2 |
| **4** | Review UI (frontend) + approve endpoints + artifact persistence | Member 3 |
| **5** | Wire blueprint → evidence pipeline; profile URLs → GitHub/LeetCode | Integration |

---

## Dependencies to add (Phase 1)

```
pymupdf          # PDF extraction (replace PyPDF2)
python-docx      # DOCX extraction
```

---

## Migration from current stubs

| Current | Action |
|---------|--------|
| `services/jd/jd_parser.py` | Deprecate → `intelligence/jd/blueprint_generator.py` |
| `services/evidence/resume_parser.py` | Deprecate → `intelligence/resume/profile_extractor.py` |
| `schemas/job.py` `RoleBlueprint` | Expand to full schema (backward-compat adapter for GitHub pipeline) |
| `POST /api/jobs` (paste text) | Keep for dev; production uses upload flow |

---

## Open items for team sync

1. **PII handling** — redact before LLM or flag only? (GDPR / compliance)
2. **Draft session storage** — Redis TTL vs DB `document_artifacts` before approve?
3. **Frontend review screen** — inline edit blueprint JSON or form fields per section?
4. **Minimum confidence threshold** — block save if critical fields below 0.5?

---

## Conclusion

This branch establishes the **Document Intelligence Platform** foundation. Implementation proceeds phase-by-phase on top of shared `Document`, `ExtractedField`, `LLMProvider`, and full `RoleBlueprint` / `CandidateProfile` schemas — not isolated parsers.
