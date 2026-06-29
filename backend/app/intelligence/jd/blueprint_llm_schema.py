"""LLM output schema for blueprint extraction — mapped to RoleBlueprint post-validation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LLMField(BaseModel):
    value: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    source: str | None = None


class LLMSkillField(BaseModel):
    name: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    source: str | None = None
    category: str | None = "technical"


class BlueprintLLMOutput(BaseModel):
    """Structured JSON-only response from blueprint extraction LLM."""

    role_title: LLMField
    experience_level: LLMField
    employment_type: LLMField | None = None
    required_skills: list[LLMSkillField] = Field(default_factory=list)
    preferred_skills: list[LLMSkillField] = Field(default_factory=list)
    responsibilities: list[LLMField] = Field(default_factory=list)
    behavioral_traits: list[LLMField] = Field(default_factory=list)
    education: list[LLMField] = Field(default_factory=list)
    certifications: list[LLMField] = Field(default_factory=list)
    domain: LLMField | None = None
    industry: LLMField | None = None
    tools: list[LLMSkillField] = Field(default_factory=list)
    success_metrics: list[LLMField] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
