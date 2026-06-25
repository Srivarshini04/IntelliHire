"""LinkedIn extraction — claims, features, scale (never skills-first)."""

from __future__ import annotations

LINKEDIN_EXTRACTION_PROMPT = """You are an engineering hiring intelligence system.

NEVER extract a skills list. Skills are useless for hiring decisions.

Extract ONLY evidence that proves engineering capability:

1. Features Built (Authentication, Scheduling, Caching, Payments, etc.)
2. Ownership (Individual | Team Lead | Contributor)
3. Scale (users, requests/day, data volume)
4. Production Responsibility (deployed systems, uptime, customers)
5. Leadership (team size, mentoring, architecture ownership)
6. Business Impact (revenue, cost savings, user growth)

Ignore: personal info, buzzwords, soft skills, generic summaries, repeated skill keywords.

For each relevant role/project return:
{
  "project_or_role": "",
  "organization": "",
  "features": ["Authentication", "Scheduling"],
  "scale": {"users": 20000},
  "ownership": "Contributor",
  "production": true,
  "leadership": false,
  "business_impact": [],
  "evidence": ["Built JWT authentication for appointment platform serving 20,000 users"],
  "confidence": 0-100
}

Return JSON only: {"experiences": [...]}"""


def build_linkedin_prompt(jd_skills: list[str], jd_capabilities: list[str], profile_text: str) -> str:
    import json

    payload = json.dumps({
        "jd_context": {
            "required_skills": jd_skills,
            "required_capabilities": jd_capabilities,
        },
        "linkedin_profile": profile_text[:12000],
    }, indent=2)
    return f"{LINKEDIN_EXTRACTION_PROMPT}\n\nInput:\n{payload}"
