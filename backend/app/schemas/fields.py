"""Confidence, provenance, and validation primitives."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ConfidenceLevel(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class SourceSpan(BaseModel):
    """Character-level provenance for UI source highlighting."""

    text: str
    page: int | None = None
    paragraph: int | None = None
    start_char: int
    end_char: int


class ExtractionProvenance(BaseModel):
    """Full provenance for audit, debugging, and model comparison."""

    field: str
    model: str = ""
    prompt_version: str = ""
    parser_version: str = ""
    extracted_at: datetime = Field(default_factory=datetime.utcnow)


class ExtractedField(BaseModel, Generic[T]):
    """Every AI extraction: value + confidence + source + provenance."""

    value: T
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    source: str | None = None
    source_span: SourceSpan | None = None
    provenance: ExtractionProvenance | None = None

    @property
    def confidence_level(self) -> ConfidenceLevel:
        if self.confidence > 0.85:
            return ConfidenceLevel.GREEN
        if self.confidence >= 0.60:
            return ConfidenceLevel.YELLOW
        return ConfidenceLevel.RED


class SkillField(BaseModel):
    skill_id: str | None = None
    name: str
    normalized_name: str
    canonical_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    source: str | None = None
    source_span: SourceSpan | None = None
    category: str | None = None
    domain: str | None = None
    provenance: ExtractionProvenance | None = None

    @property
    def confidence_level(self) -> ConfidenceLevel:
        if self.confidence > 0.85:
            return ConfidenceLevel.GREEN
        if self.confidence >= 0.60:
            return ConfidenceLevel.YELLOW
        return ConfidenceLevel.RED


CRITICAL_BLUEPRINT_FIELDS = frozenset({
    "role_title",
    "required_skills",
    "experience_level",
    "employment_type",
    "capability_weights",
})

CRITICAL_PROFILE_FIELDS = frozenset({
    "name",
    "email",
    "skills",
    "experience",
})


class FieldValidation(BaseModel):
    """Soft gate result — never block entire save."""

    field: str
    confidence_level: ConfidenceLevel
    is_critical: bool
    requires_confirmation: bool
    message: str | None = None


def validate_field(field_name: str, confidence: float, critical_fields: frozenset[str]) -> FieldValidation:
    if confidence > 0.85:
        level = ConfidenceLevel.GREEN
    elif confidence >= 0.60:
        level = ConfidenceLevel.YELLOW
    else:
        level = ConfidenceLevel.RED

    is_critical = field_name in critical_fields
    requires_confirmation = level == ConfidenceLevel.RED and is_critical

    message = None
    if level == ConfidenceLevel.YELLOW:
        message = f"Low-medium confidence ({confidence:.0%}) — please verify"
    elif requires_confirmation:
        message = f"Low confidence ({confidence:.0%}) on critical field — confirmation required"

    return FieldValidation(
        field=field_name,
        confidence_level=level,
        is_critical=is_critical,
        requires_confirmation=requires_confirmation,
        message=message,
    )


class VersioningMeta(BaseModel):
    blueprint_version: str = "1.0.0"
    parser_version: str = "1.0.0"
    prompt_version: str = "1.0.0"
    llm_model: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    approved_by: str | None = None
    approved_at: datetime | None = None


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


class HumanFeedback(BaseModel):
    """Recruiter correction — training data for prompt tuning / fine-tuning."""

    field: str
    ai_value: str
    human_value: str
    reason: str = "manual_edit"
    document_id: str | None = None
    artifact_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
