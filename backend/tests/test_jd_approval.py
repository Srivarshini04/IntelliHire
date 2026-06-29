"""Unit tests for JD approval workflow (no LLM)."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.intelligence.jd.approval_service import ApprovalError, ApprovalService
from app.intelligence.jd.approval_validator import ApprovalValidator
from app.intelligence.jd.feedback_engine import FeedbackEngine
from app.models.document_artifact import DocumentArtifactRecord
from app.models.job import Job
from app.schemas.artifacts import ArtifactType
from app.schemas.fields import ExtractedField, SkillField, VersioningMeta
from app.schemas.job import JobApproveRequest, RoleBlueprint


def _skill(name: str, confidence: float = 0.9) -> SkillField:
    return SkillField(name=name, normalized_name=name, confidence=confidence)


def _blueprint(
    *,
    title: str = "Backend Engineer",
    level: str = "senior",
    skills: list[str] | None = None,
    title_confidence: float = 0.9,
    level_confidence: float = 0.9,
    skill_confidence: float = 0.9,
    version: str = "1.0.0",
) -> RoleBlueprint:
    skill_list = skills or ["Python", "FastAPI"]
    return RoleBlueprint(
        role_title=ExtractedField(value=title, confidence=title_confidence),
        experience_level=ExtractedField(value=level, confidence=level_confidence),
        required_skills=[_skill(s, skill_confidence) for s in skill_list],
        capability_weights={
            "technical": 0.40,
            "execution": 0.25,
            "ownership": 0.20,
            "learning": 0.15,
        },
        versioning=VersioningMeta(blueprint_version=version, prompt_version="v1"),
    )


def test_feedback_engine_detects_skill_edits():
    ai = _blueprint(skills=["Python", "Java"])
    human = _blueprint(skills=["Python", "Rust"])
    feedback = FeedbackEngine.compute_diff(ai, human)
    assert "required_skills" in feedback.fields_changed
    skill_diff = next(d for d in feedback.diffs if d.field == "required_skills")
    assert "Rust" in skill_diff.added
    assert "Java" in skill_diff.removed


def test_approval_validator_red_field_requires_confirmation():
    blueprint = _blueprint(title_confidence=0.4, skill_confidence=0.9)
    result = ApprovalValidator.validate(blueprint, confirmations=[])
    assert not result.passed
    assert any("role_title" in e for e in result.errors)


def test_approval_validator_red_field_with_confirmation():
    blueprint = _blueprint(title_confidence=0.4)
    result = ApprovalValidator.validate(blueprint, confirmations=["role_title"])
    assert result.passed


def test_approval_validator_green_always_passes():
    blueprint = _blueprint(title_confidence=0.95, level_confidence=0.92)
    result = ApprovalValidator.validate(blueprint, confirmations=[])
    assert result.passed


def test_approval_validator_yellow_warning_only():
    blueprint = _blueprint(title_confidence=0.75, level_confidence=0.95)
    result = ApprovalValidator.validate(blueprint, confirmations=[])
    assert result.passed
    assert result.warnings


def test_finalize_blueprint_increments_version():
    blueprint = _blueprint(version="1.0.0")
    approved = ApprovalService._finalize_blueprint(
        blueprint,
        approved_version=2,
        approved_by="recruiter@example.com",
    )
    assert approved.versioning.blueprint_version == "2.0.0"
    assert approved.versioning.approved_by == "recruiter@example.com"
    assert approved.versioning.approved_at is not None


def test_approve_without_edits_persists_artifacts():
    document_id = uuid.uuid4()
    draft_blueprint = _blueprint()
    draft_record = DocumentArtifactRecord(
        id=uuid.uuid4(),
        document_id=document_id,
        artifact_type=ArtifactType.BLUEPRINT_DRAFT.value,
        payload=draft_blueprint.model_dump(mode="json"),
    )

    saved: list[DocumentArtifactRecord] = []

    async def fake_save(db, doc_id, artifact_type, payload, **kwargs):
        status = kwargs.get("status", "draft")
        status_value = status.value if hasattr(status, "value") else status
        record = DocumentArtifactRecord(
            id=uuid.uuid4(),
            document_id=doc_id,
            artifact_type=artifact_type.value,
            payload=payload,
            artifact_version=kwargs.get("artifact_version", 1),
            status=status_value,
        )
        saved.append(record)
        return record

    db = AsyncMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()

    with patch("app.intelligence.jd.approval_service.load_latest_artifact", new_callable=AsyncMock) as load_latest, \
         patch("app.intelligence.jd.approval_service.load_document", new_callable=AsyncMock) as load_doc, \
         patch("app.intelligence.jd.approval_service.count_artifacts", new_callable=AsyncMock) as count_art, \
         patch("app.intelligence.jd.approval_service.save_artifact", side_effect=fake_save), \
         patch.object(ApprovalService, "_upsert_job", new_callable=AsyncMock) as upsert_job:

        load_latest.return_value = draft_record
        load_doc.return_value = None
        count_art.return_value = 0
        upsert_job.return_value = Job(
            id=uuid.uuid4(),
            title="Backend Engineer",
            description="desc",
            role_blueprint={},
            document_id=document_id,
        )

        request = JobApproveRequest(
            document_id=document_id,
            blueprint=draft_blueprint,
            confirmations=[],
            approved_by="recruiter@example.com",
        )
        response = asyncio.run(ApprovalService.approve(db, request))

    assert response.status == "approved"
    artifact_types = [r.artifact_type for r in saved]
    assert ArtifactType.HUMAN_FEEDBACK.value in artifact_types
    assert ArtifactType.BLUEPRINT_APPROVED.value in artifact_types
    assert response.feedback_summary["total_changes"] == 0


def test_approve_with_edits_generates_feedback():
    document_id = uuid.uuid4()
    ai = _blueprint(skills=["Python", "Java"])
    human = _blueprint(skills=["Python", "Rust"])

    draft_record = DocumentArtifactRecord(
        id=uuid.uuid4(),
        document_id=document_id,
        artifact_type=ArtifactType.BLUEPRINT_DRAFT.value,
        payload=ai.model_dump(mode="json"),
    )

    feedback_payloads: list[dict] = []

    async def fake_save(db, doc_id, artifact_type, payload, **kwargs):
        if artifact_type == ArtifactType.HUMAN_FEEDBACK:
            feedback_payloads.append(payload)
        return DocumentArtifactRecord(
            id=uuid.uuid4(),
            document_id=doc_id,
            artifact_type=artifact_type.value,
            payload=payload,
        )

    db = AsyncMock()
    db.commit = AsyncMock()

    with patch("app.intelligence.jd.approval_service.load_latest_artifact", new_callable=AsyncMock) as load_latest, \
         patch("app.intelligence.jd.approval_service.load_document", new_callable=AsyncMock), \
         patch("app.intelligence.jd.approval_service.count_artifacts", new_callable=AsyncMock, return_value=1), \
         patch("app.intelligence.jd.approval_service.save_artifact", side_effect=fake_save), \
         patch.object(ApprovalService, "_upsert_job", new_callable=AsyncMock) as upsert_job:

        load_latest.return_value = draft_record
        upsert_job.return_value = Job(
            id=uuid.uuid4(),
            title="Backend Engineer",
            description="desc",
            role_blueprint={},
            document_id=document_id,
        )

        response = asyncio.run(
            ApprovalService.approve(
                db,
                JobApproveRequest(document_id=document_id, blueprint=human),
            )
        )

    assert response.feedback_summary["total_changes"] > 0
    assert feedback_payloads
    assert "required_skills" in feedback_payloads[0]["fields_changed"]


def test_approve_rejects_unconfirmed_red_fields():
    document_id = uuid.uuid4()
    draft = _blueprint(title_confidence=0.3)
    draft_record = DocumentArtifactRecord(
        id=uuid.uuid4(),
        document_id=document_id,
        artifact_type=ArtifactType.BLUEPRINT_DRAFT.value,
        payload=draft.model_dump(mode="json"),
    )

    db = AsyncMock()

    with patch("app.intelligence.jd.approval_service.load_latest_artifact", new_callable=AsyncMock) as load_latest:
        load_latest.return_value = draft_record
        with pytest.raises(ApprovalError) as exc:
            asyncio.run(
                ApprovalService.approve(
                    db,
                    JobApproveRequest(document_id=document_id, blueprint=draft, confirmations=[]),
                )
            )
        assert any("role_title" in e for e in exc.value.errors)
