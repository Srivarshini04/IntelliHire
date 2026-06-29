"""Document domain model — all intelligence engines consume Document, not str."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PiiPolicy(str, Enum):
    """PII handling policy for LLM calls."""

    DETECT_ONLY = "detect_only"
    MASK_EXTERNAL = "mask_external"
    MASK_ALWAYS = "mask_always"


class DocumentQuality(BaseModel):
    """Pre-parse quality score — avoid feeding garbage to LLM."""

    score: float = Field(ge=0.0, le=100.0, default=100.0)
    ocr_quality: float = 100.0
    formatting: float = 100.0
    missing_sections: float = 100.0
    image_only_pages: float = 100.0
    language_detected: str = "en"
    duplicate_text_ratio: float = 0.0
    has_tables: bool = False
    broken_encoding: bool = False
    recommend_manual_review: bool = False

    @classmethod
    def from_components(cls, **kwargs: float | bool) -> "DocumentQuality":
        components = {
            "ocr_quality": float(kwargs.get("ocr_quality", 100.0)),
            "formatting": float(kwargs.get("formatting", 100.0)),
            "missing_sections": float(kwargs.get("missing_sections", 100.0)),
            "image_only_pages": float(kwargs.get("image_only_pages", 100.0)),
        }
        score = sum(components.values()) / len(components)
        return cls(
            score=round(score, 1),
            recommend_manual_review=score < 40,
            **{k: v for k, v in kwargs.items() if k in cls.model_fields},
        )


class PiiDetectionResult(BaseModel):
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    names: list[str] = Field(default_factory=list)
    addresses: list[str] = Field(default_factory=list)
    masked_count: int = 0


# Backward-compatible alias
PiiDetection = PiiDetectionResult


class DocumentMetadata(BaseModel):
    file_size_bytes: int = 0
    page_count: int = 0
    content_hash: str | None = None
    storage_uri: str | None = None
    extractor_version: str = "1.0.0"
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    pii_policy: PiiPolicy = PiiPolicy.MASK_EXTERNAL
    extra: dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    """Structured output of the Document Understanding Layer."""

    id: UUID = Field(default_factory=uuid4)
    filename: str
    filetype: str
    pages: int = 0
    language: str = "en"
    original_text: str
    masked_text: str | None = None
    raw_text: str
    cleaned_text: str
    sections: dict[str, str] = Field(default_factory=dict)
    section_spans: dict[str, list[dict]] = Field(default_factory=dict)
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    quality: DocumentQuality = Field(default_factory=DocumentQuality)
    pii: PiiDetectionResult = Field(default_factory=PiiDetectionResult)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    extra: dict[str, Any] = Field(default_factory=dict)

    def text_for_llm(self, policy: PiiPolicy | None = None) -> str:
        """Return text safe to send to external LLM based on policy."""
        policy = policy or self.metadata.pii_policy
        if policy == PiiPolicy.MASK_ALWAYS or policy == PiiPolicy.MASK_EXTERNAL:
            return self.masked_text or self.cleaned_text
        return self.cleaned_text

    model_config = {"from_attributes": True}
