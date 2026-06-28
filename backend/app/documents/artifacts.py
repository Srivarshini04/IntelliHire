"""Document artifact persistence — Postgres audit log."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_artifact import DocumentArtifactRecord
from app.schemas.artifacts import ArtifactStatus, ArtifactType
from app.schemas.document import Document
from app.schemas.job import RoleBlueprint


async def save_artifact(
    db: AsyncSession,
    document_id: UUID,
    artifact_type: ArtifactType,
    payload: dict,
    *,
    storage_uri: str | None = None,
    status: ArtifactStatus = ArtifactStatus.DRAFT,
    created_by: str | None = None,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    artifact_version: int = 1,
) -> DocumentArtifactRecord:
    record = DocumentArtifactRecord(
        document_id=document_id,
        entity_type=entity_type,
        entity_id=entity_id,
        artifact_type=artifact_type.value,
        artifact_version=artifact_version,
        status=status.value,
        payload=payload,
        storage_uri=storage_uri,
        created_by=created_by,
    )
    db.add(record)
    await db.flush()
    return record


async def load_latest_artifact(
    db: AsyncSession,
    document_id: UUID,
    artifact_type: ArtifactType,
) -> DocumentArtifactRecord | None:
    result = await db.execute(
        select(DocumentArtifactRecord)
        .where(
            DocumentArtifactRecord.document_id == document_id,
            DocumentArtifactRecord.artifact_type == artifact_type.value,
        )
        .order_by(DocumentArtifactRecord.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_artifacts(
    db: AsyncSession,
    document_id: UUID,
    artifact_type: ArtifactType,
) -> int:
    result = await db.execute(
        select(DocumentArtifactRecord)
        .where(
            DocumentArtifactRecord.document_id == document_id,
            DocumentArtifactRecord.artifact_type == artifact_type.value,
        )
    )
    return len(result.scalars().all())


async def load_document(db: AsyncSession, document_id: UUID) -> Document | None:
    record = await load_latest_artifact(db, document_id, ArtifactType.EXTRACTED_TEXT)
    if not record:
        return None
    return Document.model_validate(record.payload)


async def load_blueprint_draft(db: AsyncSession, document_id: UUID) -> RoleBlueprint | None:
    record = await load_latest_artifact(db, document_id, ArtifactType.BLUEPRINT_DRAFT)
    if not record:
        return None
    return RoleBlueprint.model_validate(record.payload)


async def approve_artifact(db: AsyncSession, artifact_id: UUID) -> None:
    record = await db.get(DocumentArtifactRecord, artifact_id)
    if record:
        record.status = ArtifactStatus.APPROVED.value
        record.approved_at = datetime.now(timezone.utc)


async def load_latest_entity_artifact(
    db: AsyncSession,
    entity_type: str,
    entity_id: UUID,
    artifact_type: ArtifactType,
) -> DocumentArtifactRecord | None:
    result = await db.execute(
        select(DocumentArtifactRecord)
        .where(
            DocumentArtifactRecord.entity_type == entity_type,
            DocumentArtifactRecord.entity_id == entity_id,
            DocumentArtifactRecord.artifact_type == artifact_type.value,
        )
        .order_by(DocumentArtifactRecord.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_entity_artifacts(
    db: AsyncSession,
    entity_type: str,
    entity_id: UUID,
    artifact_type: ArtifactType,
) -> list[DocumentArtifactRecord]:
    result = await db.execute(
        select(DocumentArtifactRecord)
        .where(
            DocumentArtifactRecord.entity_type == entity_type,
            DocumentArtifactRecord.entity_id == entity_id,
            DocumentArtifactRecord.artifact_type == artifact_type.value,
        )
        .order_by(DocumentArtifactRecord.created_at.asc())
    )
    return list(result.scalars().all())
