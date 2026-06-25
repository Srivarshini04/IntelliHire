"""Document Intelligence API — stubs return 501 until Phase 1–3 implementation."""

from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.documents.service import build_document
from app.schemas.job import BlueprintDraftResponse, BlueprintGenerateRequest, JobUploadResponse

router = APIRouter(prefix="/jobs", tags=["document-intelligence"])


@router.post("/upload", response_model=JobUploadResponse)
async def upload_job_description(file: UploadFile = File(...)):
    """Phase 1: Extract Document from PDF/DOCX. Returns draft for recruiter review."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")
    content = await file.read()
    try:
        document = build_document(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # TODO Phase 1: persist original + extracted to document_artifacts
    return JobUploadResponse(
        document_id=document.id,
        document=document,
    )


@router.post("/blueprint", response_model=BlueprintDraftResponse)
async def generate_blueprint(request: BlueprintGenerateRequest):
    """Phase 2: Generate RoleBlueprint draft — recruiter reviews before save."""
    raise HTTPException(
        status_code=501,
        detail="Blueprint generator not implemented — see feat/jd-intelligence branch",
    )
