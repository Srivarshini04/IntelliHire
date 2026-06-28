"""Role DNA — the rich semantic representation of hiring intent.

A superset of the existing ``app.schemas.job.RoleBlueprint`` (which stays as the
extraction artifact). The RoleDNAProvider *derives* RoleDNA from a blueprint/JD;
this module only defines the contract (no derivation logic — Phase A).

RoleDNA is the basis for materiality (DECISION B) and absence detection
(DECISION C) inside the ReasoningEngine.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.shared.enums import EvidenceSource, Intensity


class RoleDNA(BaseModel):
    """What 'good' looks like for one role — beyond keywords."""

    schema_version: Literal["1.0"] = "1.0"
    role_dna_id: str = Field(..., description="Stable id, e.g. 'roledna:j1'.")
    job_id: str
    role_summary: str = Field(..., description="One-paragraph semantic summary of the role.")

    # --- explicit requirements (canonical entity refs, e.g. 'skill:fastapi') ---
    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    domain: str | None = None
    engineering_level: str | None = Field(default=None, description="e.g. 'junior'|'mid'|'senior'|'staff'.")

    # --- latent / behavioural expectations (drive materiality) ---
    ownership_level: Intensity = Intensity.MEDIUM
    ambiguity_tolerance: Intensity = Intensity.MEDIUM
    communication_need: Intensity = Intensity.MEDIUM
    learning_requirement: Intensity = Intensity.MEDIUM
    research_requirement: Intensity = Intensity.NONE
    collaboration_requirement: Intensity = Intensity.MEDIUM
    delivery_expectation: Intensity = Intensity.MEDIUM
    system_design_expectation: Intensity = Intensity.MEDIUM
    coding_requirement: Intensity = Intensity.HIGH

    culture: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    growth_path: str | None = None

    # --- ranking inputs ---
    capability_weights: dict[str, float] = Field(
        default_factory=dict,
        description="Dimension -> weight (sums to ~1.0). Reused from RoleBlueprint; basis for materiality.",
    )
    required_evidence: list[EvidenceSource] = Field(
        default_factory=list, description="Sources that must be present for a confident decision."
    )

    derived_from_blueprint_version: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
