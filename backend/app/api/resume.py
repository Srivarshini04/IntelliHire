"""Resume upload API — separate from candidate persist."""

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.documents.service import build_document

router = APIRouter(prefix="/candidates", tags=["document-intelligence"])


@router.post("/upload")
async def upload_resume(file: UploadFile = File(...)):
    """Phase 3: Extract CandidateProfile draft — recruiter reviews before save."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")
    content = await file.read()
    try:
        document = build_document(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    raise HTTPException(
        status_code=501,
        detail={
            "message": "Document extracted. Profile extraction not yet implemented.",
            "document_id": str(document.id),
            "cleaned_text_preview": document.cleaned_text[:500],
        },
    )
