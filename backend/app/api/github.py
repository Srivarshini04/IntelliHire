import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.pipeline.comparison import compare_candidates
from app.pipeline.schemas import CompareRequest
from app.services.evidence.github_service import analyze_github_evidence

router = APIRouter(prefix="/github", tags=["github"])


class GitHubAnalyzeRequest(BaseModel):
    github_url: str
    linkedin_url: str | None = None
    resume_text: str | None = None
    leetcode_url: str | None = None
    required_skills: list[str] = Field(default_factory=list)


@router.post("/analyze")
async def analyze_github(request: GitHubAnalyzeRequest):
    """Run integrated GitHub evidence analysis (basic extractor + deep pipeline)."""
    try:
        role_blueprint = {"skills": request.required_skills} if request.required_skills else None
        result = await analyze_github_evidence(
            github_url=request.github_url,
            role_blueprint=role_blueprint,
            linkedin_url=request.linkedin_url,
            resume_text=request.resume_text,
            leetcode_url=request.leetcode_url,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"GitHub analysis failed: {exc}") from exc


@router.post("/compare")
async def compare_github(request: CompareRequest):
    """Compare multiple GitHub profiles side-by-side."""
    try:
        return await asyncio.to_thread(_compare_sync, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {exc}") from exc


def _compare_sync(request: CompareRequest):
    from app.github_intel.database import SessionLocal

    db = SessionLocal()
    try:
        return compare_candidates(db, request)
    finally:
        db.close()
