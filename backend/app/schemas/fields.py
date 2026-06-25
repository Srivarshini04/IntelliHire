"""Confidence + explainability primitives for all extracted fields."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ExtractedField(BaseModel, Generic[T]):
    """Every AI extraction: value + confidence + source quote."""

    value: T
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    source: str | None = None  # verbatim snippet from document


class SkillField(BaseModel):
    """Normalized skill with confidence — never store raw strings alone."""

    name: str
    normalized_name: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    source: str | None = None
    category: str | None = None  # technical | soft | tool | domain


class VersioningMeta(BaseModel):
    blueprint_version: str = "1.0.0"
    parser_version: str = "1.0.0"
    prompt_version: str = "1.0.0"
    llm_model: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ExperienceEntry(BaseModel):
    title: ExtractedField[str]
    company: ExtractedField[str] | None = None
    duration: ExtractedField[str] | None = None
    description: ExtractedField[str] | None = None


class ProjectEntry(BaseModel):
    name: ExtractedField[str]
    description: ExtractedField[str] | None = None
    technologies: list[SkillField] = Field(default_factory=list)


class EducationEntry(BaseModel):
    degree: ExtractedField[str]
    institution: ExtractedField[str] | None = None
    year: ExtractedField[str] | None = None
