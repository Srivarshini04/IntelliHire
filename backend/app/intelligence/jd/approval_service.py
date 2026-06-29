"""Recruiter approval workflow — draft → feedback → approved."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.artifacts import (
    count_artifacts,
    load_blueprint_draft,
    load_document,
    load_latest_artifact,
    save_artifact,
)
from app.intelligence.jd.approval_validator import ApprovalValidator
from app.intelligence.jd.feedback_engine import FeedbackEngine
from app.models.job import Job
from app.schemas.artifacts import ArtifactType, ArtifactStatus
from app.schemas.fields import VersioningMeta
from app.schemas.job import JobApproveRequest, JobApproveResponse, RoleBlueprint


class ApprovalError(Exception):
    def __init__(self, message: str, errors: list[str], warnings: list[str]):
        super().__init__(message)
        self.errors = errors
        self.warnings = warnings


class ApprovalService:
    @classmethod
    async def approve(
        cls,
        db: AsyncSession,
        request: JobApproveRequest,
    ) -> JobApproveResponse:
        draft_record = await load_latest_artifact(
            db, request.document_id, ArtifactType.BLUEPRINT_DRAFT
        )
        if not draft_record:
            raise ApprovalError(
                "No BLUEPRINT_DRAFT found for document",
                errors=["missing_blueprint_draft"],
                warnings=[],
            )

        ai_blueprint = RoleBlueprint.model_validate(draft_record.payload)
        human_blueprint = request.blueprint

        validation = ApprovalValidator.validate(human_blueprint, request.confirmations)
        if not validation.passed:
            raise ApprovalError(
                "Approval validation failed",
                errors=validation.errors,
                warnings=validation.warnings,
            )

        feedback = FeedbackEngine.compute_diff(ai_blueprint, human_blueprint)
        feedback.document_id = str(request.document_id)
        feedback.draft_artifact_id = str(draft_record.id)

        approved_version = await cls._next_blueprint_version(db, request.document_id)
        approved_blueprint = cls._finalize_blueprint(
            human_blueprint,
            approved_version=approved_version,
            approved_by=request.approved_by,
        )

        feedback_record = await save_artifact(
            db,
            request.document_id,
            ArtifactType.HUMAN_FEEDBACK,
            feedback.model_dump(mode="json"),
            status=ArtifactStatus.DRAFT,
            created_by=request.approved_by,
        )

        approved_record = await save_artifact(
            db,
            request.document_id,
            ArtifactType.BLUEPRINT_APPROVED,
            approved_blueprint.model_dump(mode="json"),
            status=ArtifactStatus.APPROVED,
            created_by=request.approved_by,
            artifact_version=approved_version,
        )
        approved_record.approved_at = datetime.now(timezone.utc)

        draft_record.status = ArtifactStatus.SUPERSEDED.value

        document = await load_document(db, request.document_id)
        description = document.cleaned_text if document else approved_blueprint.role_title.value

        job = await cls._upsert_job(
            db,
            document_id=request.document_id,
            title=approved_blueprint.role_title.value,
            description=description,
            blueprint=approved_blueprint,
        )

        await db.commit()

        return JobApproveResponse(
            status="approved",
            job_id=job.id,
            artifact_id=approved_record.id,
            warnings=validation.warnings,
            feedback_summary=feedback.model_dump(mode="json"),
        )

    @staticmethod
    async def _next_blueprint_version(db: AsyncSession, document_id: UUID) -> int:
        count = await count_artifacts(db, document_id, ArtifactType.BLUEPRINT_APPROVED)
        return count + 1

    @staticmethod
    def _finalize_blueprint(
        blueprint: RoleBlueprint,
        *,
        approved_version: int,
        approved_by: str | None,
    ) -> RoleBlueprint:
        versioning = blueprint.versioning.model_copy(
            update={
                "blueprint_version": f"{approved_version}.0.0",
                "approved_by": approved_by,
                "approved_at": datetime.now(timezone.utc),
            }
        )
        return blueprint.model_copy(update={"versioning": versioning})

    @staticmethod
    async def _upsert_job(
        db: AsyncSession,
        *,
        document_id: UUID,
        title: str,
        description: str,
        blueprint: RoleBlueprint,
    ) -> Job:
        from sqlalchemy import select

        result = await db.execute(
            select(Job).where(Job.document_id == document_id).limit(1)
        )
        job = result.scalar_one_or_none()
        payload = blueprint.model_dump(mode="json")

        if job:
            job.title = title
            job.description = description
            job.role_blueprint = payload
            return job

        job = Job(
            title=title,
            description=description,
            role_blueprint=payload,
            document_id=document_id,
        )
        db.add(job)
        await db.flush()
        return job
