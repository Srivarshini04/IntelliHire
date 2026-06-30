from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.evidence.portfolio_service import analyze_portfolio_evidence

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class PortfolioAnalyzeRequest(BaseModel):
    portfolio_url: str
    required_skills: list[str] = Field(default_factory=list)


@router.post("/analyze")
async def analyze_portfolio(request: PortfolioAnalyzeRequest):
    """Fetch and analyze a candidate's portfolio site for self-reported skills."""
    try:
        role_blueprint = {"skills": request.required_skills} if request.required_skills else None
        result = await analyze_portfolio_evidence(
            portfolio_url=request.portfolio_url,
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
        raise HTTPException(status_code=500, detail=f"Portfolio analysis failed: {exc}") from exc
