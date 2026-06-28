"""Document artifact types and storage schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ArtifactType(str, Enum):
    RAW_DOCUMENT = "RAW_DOCUMENT"
    EXTRACTED_TEXT = "EXTRACTED_TEXT"
    CLEAN_TEXT = "CLEAN_TEXT"
    MASKED_TEXT = "MASKED_TEXT"
    BLUEPRINT_DRAFT = "BLUEPRINT_DRAFT"
    BLUEPRINT_EDITED = "BLUEPRINT_EDITED"
    BLUEPRINT_APPROVED = "BLUEPRINT_APPROVED"
    PROFILE_DRAFT = "PROFILE_DRAFT"
    PROFILE_EDITED = "PROFILE_EDITED"
    PROFILE_APPROVED = "PROFILE_APPROVED"
    HUMAN_FEEDBACK = "HUMAN_FEEDBACK"
    BLUEPRINT_DIFF = "BLUEPRINT_DIFF"
    BLUEPRINT_METRICS = "BLUEPRINT_METRICS"
    ROLE_CLASSIFICATION = "ROLE_CLASSIFICATION"
    CANDIDATE_GRAPH = "CANDIDATE_GRAPH"
    EVIDENCE_LEDGER = "EVIDENCE_LEDGER"


class ArtifactStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class DocumentArtifact(BaseModel):
    id: UUID
    document_id: UUID
    artifact_type: ArtifactType
    artifact_version: int = 1
    status: ArtifactStatus = ArtifactStatus.DRAFT
    payload: dict[str, Any]
    storage_uri: str | None = None
    created_by: str | None = None
    created_at: datetime
    approved_at: datetime | None = None

    model_config = {"from_attributes": True}


class BlueprintDiffItem(BaseModel):
    field: str
    change_type: str
    old_value: Any = None
    new_value: Any = None


class BlueprintDiff(BaseModel):
    old_artifact_id: UUID | None = None
    new_artifact_id: UUID | None = None
    changes: list[BlueprintDiffItem] = Field(default_factory=list)
    summary: str = ""
