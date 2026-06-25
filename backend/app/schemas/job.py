"""Full RoleBlueprint schema — single source of truth for hiring criteria."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.document import Document
from app.schemas.fields import ExtractedField, SkillField, VersioningMeta


class RoleBlueprint(BaseModel):
    role_title: ExtractedField[str]
    experience_level: ExtractedField[str]  # junior | mid | senior | lead
    required_skills: list[SkillField] = Field(default_factory=list)
    preferred_skills: list[SkillField] = Field(default_factory=list)
    responsibilities: list[ExtractedField[str]] = Field(default_factory=list)
    behavioral_traits: list[ExtractedField[str]] = Field(default_factory=list)
    education: list[ExtractedField[str]] = Field(default_factory=list)
    certifications: list[ExtractedField[str]] = Field(default_factory=list)
    domain: ExtractedField[str] | None = None
    industry: ExtractedField[str] | None = None
    tools: list[SkillField] = Field(default_factory=list)
    success_metrics: list[ExtractedField[str]] = Field(default_factory=list)
    capability_weights: dict[str, float] = Field(default_factory=dict)
    required_evidence: list[str] = Field(default_factory=list)
    versioning: VersioningMeta = Field(default_factory=VersioningMeta)

    @field_validator("capability_weights")
    @classmethod
    def weights_sum_to_one(cls, v: dict[str, float]) -> dict[str, float]:
        if not v:
            return v
        total = sum(v.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"capability_weights must sum to 1.0, got {total}")
        return v

    def required_skill_names(self) -> list[str]:
        return [s.normalized_name for s in self.required_skills]

    def to_legacy_dict(self) -> dict:
        """Adapter for GitHub/evidence pipeline until fully migrated."""
        return {
            "role": self.role_title.value,
            "skills": self.required_skill_names(),
            "behavioral_traits": [t.value for t in self.behavioral_traits],
            "weights": self.capability_weights,
            "required_evidence": self.required_evidence,
        }


class JobUploadResponse(BaseModel):
    document_id: UUID
    document: Document
    message: str = "Document extracted. Review text, then generate blueprint."


class BlueprintGenerateRequest(BaseModel):
    document_id: UUID | None = None
    text: str | None = None


class BlueprintDraftResponse(BaseModel):
    blueprint: RoleBlueprint
    document_id: UUID | None = None
    status: str = "draft"


class JobApproveRequest(BaseModel):
    title: str
    description: str
    blueprint: RoleBlueprint
    document_id: UUID | None = None


class JobCreate(BaseModel):
    title: str
    description: str


class JobResponse(BaseModel):
    job_id: UUID
    title: str
    description: str
    role_blueprint: RoleBlueprint | dict | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
