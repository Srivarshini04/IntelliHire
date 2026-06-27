from fastapi import APIRouter

from app.api import analysis, candidates, documents, github, jobs, linkedin, rankings, resume

api_router = APIRouter(prefix="/api")
api_router.include_router(jobs.router)
api_router.include_router(documents.router)
api_router.include_router(candidates.router)
api_router.include_router(resume.router)
api_router.include_router(rankings.router)
api_router.include_router(analysis.router)
api_router.include_router(github.router)
api_router.include_router(linkedin.router)
