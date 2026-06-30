"""Aggregating router for the DELULU v2 API.

Exposes ``router`` — an ``APIRouter(prefix="/v2")`` that mounts the six
per-resource stub routers. Mount in the app with::

    from app.api.v2.router import router as v2_router
    app.include_router(v2_router)
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v2.routes import (
    decision,
    evaluations,
    evidence,
    graph,
    ranking,
    reasoning,
    role_dna,
)

router = APIRouter(prefix="/v2")

# Primary, frontend-facing business API (Evaluation / Ranking).
router.include_router(evaluations.router)

# Internal/admin/debug — single-stage endpoints. NOT the frontend integration point.
router.include_router(evidence.router)
router.include_router(graph.router)
router.include_router(role_dna.router)
router.include_router(reasoning.router)
router.include_router(decision.router)
router.include_router(ranking.router)

__all__ = ["router"]
