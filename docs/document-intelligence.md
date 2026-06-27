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

## Locked decisions (final)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **PII** | Detect → Minimize → Configurable Redaction | Preserve context; mask for external LLM only |
| **Draft storage** | Postgres `document_artifacts` + object storage | Drafts are business data, not cache |
| **Review UI** | Structured forms + source highlighting | Recruiters are not developers |
| **Confidence** | Soft gate, field-level | Never block entire save |

---

## PII pipeline

```text
PDF/DOCX → Extract → PII Detection → Policy Engine
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    ▼                                           ▼
            Internal model                               External model (Gemini)
            Send original                                Send masked text
```

**Mask tokens:** `<EMAIL>`, `<PHONE>`, `<CANDIDATE_NAME>`  
**Never overwrite:** store both `original_text` and `masked_text` on `Document`.

**Policy env:** `PII_POLICY=detect_only|mask_external|mask_always` (default: `mask_external`)

---

## Artifact storage

**Postgres table:** `document_artifacts`

| Column | Type |
|--------|------|
| `id` | UUID |
| `document_id` | UUID |
| `artifact_type` | enum string |
| `artifact_version` | int |
| `status` | draft \| pending_review \| approved \| superseded |
| `payload` | JSONB |
| `storage_uri` | text (for RAW_DOCUMENT) |
| `created_by` | string |
| `created_at` | timestamp |
| `approved_at` | timestamp |

**Artifact types:** `RAW_DOCUMENT`, `EXTRACTED_TEXT`, `CLEAN_TEXT`, `MASKED_TEXT`, `BLUEPRINT_DRAFT`, `BLUEPRINT_EDITED`, `BLUEPRINT_APPROVED`, `PROFILE_DRAFT`, `PROFILE_EDITED`, `PROFILE_APPROVED`, `HUMAN_FEEDBACK`, `BLUEPRINT_DIFF`

**Binary files:** MinIO/S3 (`OBJECT_STORAGE_BACKEND=local|s3|minio`). Postgres stores pointer only.

---

## Review UI specification (Member 3)

Structured forms — **not JSON editing.**

```
Role Title          [ Senior Backend Engineer ]     🟢 92%  [View Source]
Required Skills     ☑ Python  ☑ FastAPI  ☐ K8s     🟡 78%  [View Source]
Experience          [ 5-8 years ]                   🟢 96%  [View Source]
```

**View Source** → highlights sentence in JD (ChatGPT-style citation).

**Internal model:** `SourceSpan` — `page`, `paragraph`, `start_char`, `end_char`

---

## Confidence gates (soft)

| Level | Range | UX |
|-------|-------|-----|
| 🟢 GREEN | > 0.85 | Save |
| 🟡 YELLOW | 0.60–0.85 | Warn |
| 🔴 RED | < 0.60 | Require confirmation **on critical fields only** |

**Critical blueprint fields:** `role_title`, `required_skills`, `experience_level`, `employment_type`  
**Non-critical:** `preferred_skills`, `certifications` — low confidence OK

---

## Human Feedback Engine

Every recruiter edit → `HUMAN_FEEDBACK` artifact:

```json
{
  "field": "required_skills",
  "ai_value": "React",
  "human_value": "Next.js",
  "reason": "manual_edit"
}
```

Builds fine-tuning dataset over time.

---

## Document Quality Score

Scored **before** LLM extraction. Components: OCR quality, formatting, missing sections, image-only pages, duplicate text, broken encoding, tables.

If score **< 40** → recommend manual review or OCR before blueprint generation.

---

## Extraction Provenance

Every field retains:

```json
{
  "field": "experience_level",
  "value": "Senior",
  "confidence": 0.96,
  "source_span": { "page": 3, "start_char": 412, "end_char": 427, "text": "5+ years..." },
  "provenance": { "model": "gemini-2.0-flash", "prompt_version": "v1" }
}
```

---

## Blueprint Diff

When JD revised months later → semantic diff, not full regeneration:

```
+ Kubernetes    + Rust    - Java
experience: 5 years → 7 years
```

Enables incremental ranking updates vs full recompute.

---

## Phase 1 implementation order

1. Document artifact storage (Postgres + object storage) ✅ scaffolded
2. PII detection and masking pipeline ✅ scaffolded
3. Section detection with source spans
4. Document quality scoring ✅ scaffolded
5. Field confidence + provenance metadata ✅ schema
6. Review UI (structured forms + source highlighting)
7. Recruiter feedback capture ✅ scaffolded
8. Blueprint diff engine ✅ scaffolded

---

## Conclusion

All architectural decisions are **locked**. Implementation proceeds on `feat/jd-intelligence` and `feat/resume-intelligence` branches forked from `feat/document-understanding-engines`.
