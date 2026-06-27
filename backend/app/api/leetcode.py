import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.evidence.leetcode_engine import LeetCodeEvaluator

router = APIRouter(prefix="/leetcode", tags=["leetcode"])


class LeetCodeEvaluateRequest(BaseModel):
    leetcode_url: str


class LeetCodeEvaluateResponse(BaseModel):
    username: str
    easy_solved: int
    medium_solved: int
    hard_solved: int
    total_solved: int
    # Recruiter-facing scores (0-100). Mapped from the engine's internal
    # breakdown — the evaluation logic itself is untouched.
    problem_solving: float
    algorithm_depth: float
    coding_skill: float
    strengths: list[str]
    improvements: list[str]
    # Optional bonus signals surfaced by the engine.
    tier: str | None = None
    ranking: int | None = None
    acceptance_rate: float | None = None
    contest_rating: float | None = None


@router.post("/evaluate", response_model=LeetCodeEvaluateResponse)
async def evaluate_leetcode(request: LeetCodeEvaluateRequest) -> LeetCodeEvaluateResponse:
    """Evaluate a candidate's public LeetCode profile.

    Thin transport layer over ``LeetCodeEvaluator``. The engine is blocking
    (network I/O via ``requests``), so it runs in a threadpool to keep the
    event loop responsive.
    """
    try:
        result = await asyncio.to_thread(LeetCodeEvaluator.evaluate, request.leetcode_url)
    except ValueError as exc:
        # Invalid URL / username, or user not found.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # upstream LeetCode/network failure
        raise HTTPException(
            status_code=502, detail=f"LeetCode evaluation failed: {exc}"
        ) from exc

    return LeetCodeEvaluateResponse(
        username=result["username"],
        easy_solved=result["easy_solved"],
        medium_solved=result["medium_solved"],
        hard_solved=result["hard_solved"],
        total_solved=result["total_solved"],
        problem_solving=result["volume"],
        algorithm_depth=result["mastery"],
        coding_skill=result["coding_skill"],
        strengths=result["strengths"],
        improvements=result["improvements"],
        tier=result.get("tier"),
        ranking=result.get("ranking"),
        acceptance_rate=result.get("acceptance_rate"),
        contest_rating=result.get("contest_rating"),
    )
