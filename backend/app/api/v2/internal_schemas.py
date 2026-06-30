"""Internal/debug request schemas for the per-stage v2 endpoints.

These endpoints are NOT the frontend API — they exist to exercise a single pipeline
stage in isolation (admin/debug/QA). Unlike the business API, they intentionally accept
pipeline objects directly so a stage can be run without persistence. Kept separate from
``app.api.v2.schemas`` (Developer 1's frozen request contracts) so those stay untouched.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.shared.models import CandidateGraph, CandidateReasoning, RoleDNA


class RunReasoningDebugRequest(BaseModel):
    """Run the ReasoningEngine over an explicit graph + role (debug)."""

    graph: CandidateGraph
    role: RoleDNA


class GenerateDecisionDebugRequest(BaseModel):
    """Run the DecisionEngine over an explicit reasoning + role (debug)."""

    reasoning: CandidateReasoning
    role: RoleDNA
