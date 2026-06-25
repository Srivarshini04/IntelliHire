"""Document domain model — all intelligence engines consume Document, not str."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    file_size_bytes: int = 0
    page_count: int = 0
    content_hash: str | None = None
    extractor_version: str = "1.0.0"
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    extra: dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    """Structured output of the Document Understanding Layer."""

    id: UUID = Field(default_factory=uuid4)
    filename: str
    filetype: str  # pdf | docx
    pages: int = 0
    language: str = "en"
    raw_text: str
    cleaned_text: str
    sections: dict[str, str] = Field(default_factory=dict)
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)

    model_config = {"from_attributes": True}
