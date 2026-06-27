"""Document quality scoring — score before LLM extraction."""

from __future__ import annotations

import re

from app.schemas.document import DocumentQuality


def score_document_quality(
    text: str,
    page_count: int = 1,
    filetype: str = "pdf",
) -> DocumentQuality:
    """Heuristic quality score 0–100. Phase 1+ adds OCR analysis."""
    if not text or len(text.strip()) < 20:
        return DocumentQuality.from_components(
            ocr_quality=10.0,
            formatting=10.0,
            missing_sections=10.0,
            image_only_pages=10.0,
            broken_encoding=True,
        )

    # Broken encoding detection
    broken = bool(re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", text))
    encoding_score = 20.0 if broken else 100.0

    # Image-only pages heuristic: very little text per page
    chars_per_page = len(text) / max(page_count, 1)
    image_score = 100.0 if chars_per_page > 200 else max(20.0, chars_per_page / 2)

    # Formatting: presence of section-like headers
    has_sections = bool(re.search(
        r"(?i)(requirements|responsibilities|qualifications|experience|skills|education)",
        text,
    ))
    section_score = 90.0 if has_sections else 50.0

    # Duplicate text ratio
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    unique_ratio = len(set(lines)) / max(len(lines), 1)
    dup_penalty = unique_ratio * 100

    # OCR quality proxy: garbled character ratio
    garbled = len(re.findall(r"[^\w\s.,;:!?\-@/()%+#'\"\n]", text))
    ocr_score = max(0.0, 100.0 - (garbled / max(len(text), 1)) * 500)

    has_tables = "|" in text or "\t" in text

    quality = DocumentQuality.from_components(
        ocr_quality=ocr_score,
        formatting=section_score,
        missing_sections=section_score,
        image_only_pages=image_score,
        duplicate_text_ratio=round(1 - unique_ratio, 3),
        broken_encoding=broken,
        has_tables=has_tables,
    )
    quality.score = round(
        (ocr_score * 0.25 + encoding_score * 0.15 + image_score * 0.25 +
         section_score * 0.20 + dup_penalty * 0.15),
        1,
    )
    quality.recommend_manual_review = quality.score < 40
    return quality
