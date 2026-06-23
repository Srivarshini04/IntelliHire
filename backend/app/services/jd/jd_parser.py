"""JD Parser — Member 1: feat/job-intelligence"""

from app.schemas.job import RoleBlueprint


async def parse_job_description(title: str, description: str) -> RoleBlueprint:
    """Parse JD and generate role blueprint. TODO: integrate Gemini."""
    return RoleBlueprint(
        role=title,
        skills=["Python", "LLMs", "FastAPI"],
        behavioral_traits=["Ownership", "Execution", "Learning"],
        weights={
            "technical": 0.35,
            "execution": 0.25,
            "ownership": 0.20,
            "learning": 0.20,
        },
        required_evidence=["projects", "github", "production_systems"],
    )
