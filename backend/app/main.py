from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.api.v2.router import router as v2_router
from app.core.config import settings
from app.core.database import init_db
from app.github_intel.database import init_github_intel_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    init_github_intel_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="DELULU — AI Hiring Intelligence Platform",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(v2_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "delulu-api", "version": "0.2.0"}
