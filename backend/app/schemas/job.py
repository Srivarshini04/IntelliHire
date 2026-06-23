from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RoleBlueprint(BaseModel):
    role: str
    skills: list[str] = Field(default_factory=list)
    behavioral_traits: list[str] = Field(default_factory=list)
    weights: dict[str, float] = Field(default_factory=dict)
    required_evidence: list[str] = Field(default_factory=list)


class JobCreate(BaseModel):
    title: str
    description: str


class JobResponse(BaseModel):
    job_id: UUID
    title: str
    description: str
    role_blueprint: RoleBlueprint | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
