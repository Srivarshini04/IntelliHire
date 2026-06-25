"""GitHub Parser — integrates teammate REST extractor + delulu deep pipeline."""

from app.services.evidence.github_service import analyze_github_evidence


async def parse_github(
    github_url: str,
    role_blueprint: dict | None = None,
    linkedin_url: str | None = None,
    resume_text: str | None = None,
    leetcode_url: str | None = None,
) -> dict:
    return await analyze_github_evidence(
        github_url=github_url,
        role_blueprint=role_blueprint,
        linkedin_url=linkedin_url,
        resume_text=resume_text,
        leetcode_url=leetcode_url,
    )
