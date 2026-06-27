# API Contracts

Base URL: `http://localhost:8000/api`

## Create Job

```
POST /jobs
```

**Request:**
```json
{
  "title": "AI Engineer",
  "description": "Senior AI Engineer with Python, LLMs, FastAPI..."
}
```

**Response:**
```json
{
  "job_id": "uuid",
  "title": "AI Engineer",
  "description": "...",
  "role_blueprint": {
    "role": "AI Engineer",
    "skills": ["Python", "LLMs", "FastAPI"],
    "behavioral_traits": ["Ownership", "Execution", "Learning"],
    "weights": { "technical": 0.35, "execution": 0.25, "ownership": 0.20, "learning": 0.20 }
  }
}
```

## Upload Candidate

```
POST /candidates
Content-Type: multipart/form-data
```

| Field | Type | Required |
|-------|------|----------|
| job_id | UUID | Yes |
| name | string | Yes |
| email | string | No |
| github_url | string | No |
| linkedin_url | string | No |
| resume | file | No |

**Response:**
```json
{ "candidate_id": "uuid", "job_id": "uuid", "name": "Venu" }
```

## Analyze Candidate

```
POST /candidates/{id}/analyze
```

**Response:**
```json
{ "status": "completed", "candidate_id": "uuid" }
```

## Get Rankings

```
GET /jobs/{job_id}/rankings
```

**Response:**
```json
[
  {
    "candidate_id": "uuid",
    "candidate": "Venu",
    "fit_score": 91,
    "risk": 18,
    "hti": 66,
    "confidence": 92,
    "rank": 1,
    "recommendation": "Interview"
  }
]
```

## Candidate Detail

```
GET /candidates/{id}
```

**Response:**
```json
{
  "candidate_id": "uuid",
  "name": "Venu",
  "capability": { "technical": 88, "execution": 91, "ownership": 90, "learning_velocity": 94, "capability_score": 91 },
  "risk": { "evidence_risk": 12, "role_gap_risk": 22, "credibility_risk": 15, "risk_score": 18 },
  "hti": { "visibility_score": 25, "hti_score": 66 },
  "evidence": [],
  "explanation": {
    "strengths": ["Strong execution", "High ownership"],
    "risks": ["Limited enterprise scale"],
    "reason": "Candidate shows strong evidence of AI system delivery."
  }
}
```

## Health Check

```
GET /health
```

**Response:** `{ "status": "ok", "service": "delulu-api" }`

---

## Document Intelligence (feat/document-understanding-engines)

See [document-intelligence.md](./document-intelligence.md) for full architecture.

### Upload Job Description

```
POST /jobs/upload
Content-Type: multipart/form-data
```

**Input:** PDF or DOCX file

**Response:**
```json
{
  "document_id": "uuid",
  "document": {
    "filename": "Senior_AI_Engineer.pdf",
    "filetype": "pdf",
    "pages": 2,
    "language": "en",
    "raw_text": "...",
    "cleaned_text": "...",
    "sections": {},
    "confidence": 0.98
  },
  "message": "Document extracted. Review text, then generate blueprint."
}
```

### Generate Blueprint (draft)

```
POST /jobs/blueprint
```

**Request:**
```json
{
  "document_id": "uuid",
  "text": "optional reviewed text override"
}
```

**Response:** Full `RoleBlueprint` with `ExtractedField` confidence + `versioning` metadata. Status: `draft`.

### Approve & Save Job

```
POST /jobs
```

**Request:** `JobApproveRequest` — recruiter-edited blueprint after review.

### Upload Resume (draft)

```
POST /candidates/upload
Content-Type: multipart/form-data
```

**Response:** `CandidateProfile` draft with confidence per field. Review before `POST /candidates`.

### ExtractedField shape (all AI fields)

```json
{
  "value": "Senior",
  "confidence": 0.94,
  "source": "5+ years of backend engineering experience required"
}
```

### Confidence gate (soft)

Critical fields with RED confidence require explicit `confirmations` map:

```json
POST /jobs
{
  "title": "...",
  "description": "...",
  "blueprint": { ... },
  "confirmations": { "experience_level": true }
}
```

Non-critical low-confidence fields (e.g. preferred certifications at 0.41) do not block save.

### Human feedback (on recruiter edit)

Stored as `HUMAN_FEEDBACK` artifact when recruiter changes AI value:

```json
{ "field": "required_skills", "ai_value": "React", "human_value": "Next.js", "reason": "manual_edit" }
```

### Document quality (in upload response)

```json
"quality": { "score": 87, "recommend_manual_review": false }
```

If `score < 40`, UI should prompt OCR or manual review before blueprint generation.

