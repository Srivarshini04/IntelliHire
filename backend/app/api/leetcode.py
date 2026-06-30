from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.evidence.leetcode_service import analyze_leetcode_evidence

router = APIRouter(prefix="/leetcode", tags=["leetcode"])


class LeetCodeAnalyzeRequest(BaseModel):
    leetcode_url: str
    required_skills: list[str] = Field(default_factory=list)


@router.post("/analyze")
async def analyze_leetcode(request: LeetCodeAnalyzeRequest):
    """Evaluate a LeetCode profile (DELULU v2 coding-skill engine)."""
    try:
        role_blueprint = {"skills": request.required_skills} if request.required_skills else None
        result = await analyze_leetcode_evidence(
            leetcode_url=request.leetcode_url,
            role_blueprint=role_blueprint,
        )
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"LeetCode analysis failed: {exc}") from exc
