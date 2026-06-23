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
