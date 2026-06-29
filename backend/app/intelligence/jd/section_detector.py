"""Semantic section detection with source spans."""

from __future__ import annotations

import re

from app.schemas.document import Document
from app.schemas.sections import SECTION_PATTERNS, DocumentSection, SectionType


class SectionDetector:
    """Split document into semantic sections for targeted LLM extraction."""

    @classmethod
    def detect(cls, document: Document) -> list[DocumentSection]:
        text = document.cleaned_text
        if not text.strip():
            return [
                DocumentSection(
                    name=SectionType.OTHER,
                    title="body",
                    text="",
                    start_char=0,
                    end_char=0,
                    confidence=0.0,
                )
            ]

        lines = text.split("\n")
        sections: list[DocumentSection] = []
        current_type = SectionType.ROLE_SUMMARY
        current_title = "Role Summary"
        current_lines: list[str] = []
        char_offset = 0
        section_start = 0

        def flush(end_char: int) -> None:
            nonlocal current_lines, section_start
            body = "\n".join(current_lines).strip()
            if body:
                sections.append(
                    DocumentSection(
                        name=current_type,
                        title=current_title,
                        text=body,
                        start_char=section_start,
                        end_char=end_char,
                        confidence=0.85 if current_type != SectionType.OTHER else 0.6,
                    )
                )
            current_lines = []

        for line in lines:
            line_start = char_offset
            matched_type: SectionType | None = None
            matched_title = line.strip()

            for section_type, pattern in SECTION_PATTERNS:
                if re.match(pattern, line.strip()):
                    matched_type = section_type
                    break

            if matched_type and current_lines:
                flush(line_start)
                section_start = line_start

            if matched_type:
                current_type = matched_type
                current_title = matched_title
                char_offset += len(line) + 1
                continue

            current_lines.append(line)
            char_offset += len(line) + 1

        flush(len(text))

        if len(sections) <= 1 and text:
            return [
                DocumentSection(
                    name=SectionType.OTHER,
                    title="full_document",
                    text=text,
                    start_char=0,
                    end_char=len(text),
                    confidence=0.7,
                )
            ]

        return sections

    @classmethod
    def sections_to_dict(cls, sections: list[DocumentSection]) -> dict[str, str]:
        return {s.name.value: s.text for s in sections}
