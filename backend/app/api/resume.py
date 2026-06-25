"""Resume upload API — extract profile draft for recruiter review."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.documents.artifacts import save_artifact
from app.documents.service import build_document
from app.documents.storage import get_object_storage
from app.intelligence.resume.identity_resolver import detect_possible_duplicates
from app.intelligence.resume.profile_extractor import extract_profile
from app.schemas.artifacts import ArtifactType
from app.schemas.candidate import ResumeUploadResponse

router = APIRouter(prefix="/candidates", tags=["document-intelligence"])


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Extract CandidateProfile draft. Recruiter approval happens separately."""
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

    profile = await extract_profile(document, db=db)
    warnings = await detect_possible_duplicates(db, profile)

    message = "Profile extracted. Review before saving candidate."
    if warnings:
        message = "Profile extracted with duplicate-candidate warnings. Review before saving candidate."

    return ResumeUploadResponse(
        document_id=document.id,
        document=document,
        profile=profile,
        status="draft",
        warnings=warnings,
        message=message,
    )
