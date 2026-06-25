"""JD Parser — legacy paste-text flow. Use intelligence/jd/blueprint_generator for file upload."""

from app.skills.normalizer import normalize_skills


async def parse_job_description(title: str, description: str) -> dict:
    """Temporary stub for POST /jobs paste flow. Returns legacy dict."""
    skills = normalize_skills(["Python", "LLMs", "FastAPI"])
    return {
        "role": title,
        "skills": skills,
        "behavioral_traits": ["Ownership", "Execution", "Learning"],
        "weights": {
            "technical": 0.35,
            "execution": 0.25,
            "ownership": 0.20,
            "learning": 0.20,
        },
        "required_evidence": ["projects", "github", "production_systems"],
        "_note": "legacy stub — use POST /jobs/upload + /jobs/blueprint for full schema",
    }
