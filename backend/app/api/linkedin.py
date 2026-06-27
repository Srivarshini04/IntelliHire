from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.evidence.linkedin_service import analyze_linkedin_evidence

router = APIRouter(prefix="/linkedin", tags=["linkedin"])


class LinkedInAnalyzeRequest(BaseModel):
    linkedin_url: str
    resume_text: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)


@router.post("/analyze")
async def analyze_linkedin(request: LinkedInAnalyzeRequest):
    """Run integrated LinkedIn evidence analysis (Apify extractor + LLM pipeline)."""
    try:
        role_blueprint = None
        if request.required_skills or request.required_capabilities:
            role_blueprint = {
                "skills": request.required_skills,
                "capabilities": request.required_capabilities,
            }
        result = await analyze_linkedin_evidence(
            linkedin_url=request.linkedin_url,
            role_blueprint=role_blueprint,
            resume_text=request.resume_text,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LinkedIn analysis failed: {exc}") from exc
