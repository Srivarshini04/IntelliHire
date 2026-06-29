"""Document section models for JD intelligence pipeline."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SectionType(str, Enum):
    COMPANY = "company"
    ROLE_SUMMARY = "role_summary"
    RESPONSIBILITIES = "responsibilities"
    REQUIRED_SKILLS = "required_skills"
    PREFERRED_SKILLS = "preferred_skills"
    QUALIFICATIONS = "qualifications"
    EDUCATION = "education"
    BENEFITS = "benefits"
    LOCATION = "location"
    COMPENSATION = "compensation"
    APPLICATION = "application_instructions"
    OTHER = "other"


# Header patterns → section type
SECTION_PATTERNS: list[tuple[SectionType, str]] = [
    (SectionType.COMPANY, r"(?i)^(?:about\s+(?:the\s+)?company|company\s+overview|who\s+we\s+are)"),
    (SectionType.ROLE_SUMMARY, r"(?i)^(?:role\s+summary|position\s+summary|job\s+summary|overview|about\s+(?:the\s+)?role)"),
    (SectionType.RESPONSIBILITIES, r"(?i)^(?:responsibilities|what\s+you(?:'ll| will)\s+do|key\s+responsibilities|duties)"),
    (SectionType.REQUIRED_SKILLS, r"(?i)^(?:required\s+skills|must\s+have|minimum\s+qualifications|requirements|technical\s+skills)"),
    (SectionType.PREFERRED_SKILLS, r"(?i)^(?:preferred\s+skills|nice\s+to\s+have|bonus\s+skills|desired\s+skills)"),
    (SectionType.QUALIFICATIONS, r"(?i)^(?:qualifications|requirements|what\s+we(?:'re| are)\s+looking\s+for)"),
    (SectionType.EDUCATION, r"(?i)^(?:education|academic\s+requirements|degree\s+requirements)"),
    (SectionType.BENEFITS, r"(?i)^(?:benefits|perks|what\s+we\s+offer)"),
    (SectionType.LOCATION, r"(?i)^(?:location|work\s+location|where\s+you(?:'ll| will)\s+work)"),
    (SectionType.COMPENSATION, r"(?i)^(?:compensation|salary|pay\s+range)"),
    (SectionType.APPLICATION, r"(?i)^(?:how\s+to\s+apply|application\s+instructions|apply\s+now)"),
]


class DocumentSection(BaseModel):
    name: SectionType
    title: str
    text: str
    start_char: int
    end_char: int
    page: int | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
