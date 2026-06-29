"""Document upload and blueprint intelligence API."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.documents.artifacts import load_document, save_artifact
from app.documents.service import build_document, build_document_from_text
from app.documents.storage import get_object_storage
from app.intelligence.jd.approval_service import ApprovalError, ApprovalService
from app.intelligence.jd.orchestrator import BlueprintGenerationError, BlueprintGenerationOrchestrator
from app.schemas.artifacts import ArtifactType
from app.schemas.job import (
    BlueprintDraftResponse,
    BlueprintGenerateRequest,
    JobApproveRequest,
    JobApproveResponse,
    JobUploadResponse,
)

router = APIRouter(prefix="/jobs", tags=["document-intelligence"])


@router.post("/upload", response_model=JobUploadResponse)
async def upload_job_description(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    content = await file.read()
    try:
        document = build_document(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    storage = get_object_storage()
    storage_uri = storage.store(document.id, file.filename, content)

    await save_artifact(
        db,
        document.id,
        ArtifactType.RAW_DOCUMENT,
        {"filename": file.filename, "filetype": document.filetype},
        storage_uri=storage_uri,
    )
    await save_artifact(
        db,
        document.id,
        ArtifactType.EXTRACTED_TEXT,
        document.model_dump(mode="json"),
    )
    await save_artifact(
        db,
        document.id,
        ArtifactType.CLEAN_TEXT,
        {"cleaned_text": document.cleaned_text, "sections": document.sections},
    )
    if document.masked_text:
        await save_artifact(
            db,
            document.id,
            ArtifactType.MASKED_TEXT,
            {"masked_text": document.masked_text, "pii": document.pii.model_dump()},
        )
    await db.commit()

    message = "Document extracted. Review text, then generate blueprint."
    if document.quality.recommend_manual_review:
        message = (
            f"Document quality score {document.quality.score}/100 — "
            "manual review or OCR recommended before blueprint generation."
        )

    return JobUploadResponse(document_id=document.id, document=document, message=message)


@router.post("/blueprint", response_model=BlueprintDraftResponse)
async def generate_blueprint(
    request: BlueprintGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    if request.document_id:
        document = await load_document(db, request.document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
    elif request.text:
        document = build_document_from_text(request.text)
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide document_id from /jobs/upload or raw text",
        )

    try:
        blueprint, classification, metrics = await BlueprintGenerationOrchestrator.run(
            document,
            db=db,
        )
    except BlueprintGenerationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(exc),
                "metrics": exc.metrics.model_dump(mode="json"),
            },
        ) from exc

    return BlueprintDraftResponse(
        blueprint=blueprint,
        document_id=document.id,
        status=metrics.status,
        classification=classification.model_dump(),
        metrics=metrics.model_dump(mode="json"),
        warnings=metrics.validation_warnings,
    )


@router.post("/approve", response_model=JobApproveResponse)
async def approve_blueprint(
    request: JobApproveRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await ApprovalService.approve(db, request)
    except ApprovalError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(exc),
                "errors": exc.errors,
                "warnings": exc.warnings,
            },
        ) from exc
