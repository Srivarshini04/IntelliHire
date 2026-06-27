"""Human Feedback Engine — capture recruiter corrections as training data."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.artifacts import save_artifact
from app.schemas.artifacts import ArtifactType, ArtifactStatus
from app.schemas.fields import HumanFeedback


async def record_feedback(
    db: AsyncSession,
    document_id: UUID,
    feedback: HumanFeedback,
    created_by: str | None = None,
) -> None:
    """Store recruiter edit as HUMAN_FEEDBACK artifact."""
    await save_artifact(
        db,
        document_id=document_id,
        artifact_type=ArtifactType.HUMAN_FEEDBACK,
        payload=feedback.model_dump(mode="json"),
        status=ArtifactStatus.APPROVED,
        created_by=created_by,
    )


def diff_field(ai_value: str, human_value: str, field: str) -> HumanFeedback | None:
    if ai_value.strip() == human_value.strip():
        return None
    return HumanFeedback(
        field=field,
        ai_value=ai_value,
        human_value=human_value,
        reason="manual_edit",
    )
