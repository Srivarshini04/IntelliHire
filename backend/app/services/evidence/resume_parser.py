"""Resume Parser — Member 2: feat/resume-parser"""


async def parse_resume(file_path: str) -> dict:
    """Extract skills, projects, experience, education from resume PDF."""
    return {
        "skills": [],
        "projects": [],
        "experience": [],
        "education": [],
    }
