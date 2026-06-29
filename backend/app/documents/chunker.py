"""Section chunking for LLM context windows."""

from __future__ import annotations

import re


def detect_sections(text: str) -> dict[str, str]:
    """Heuristic section split — LLM refinement in Phase 2."""
    headers = re.split(
        r"\n(?=(?:REQUIREMENTS|RESPONSIBILITIES|QUALIFICATIONS|EXPERIENCE|SKILLS|EDUCATION|ABOUT)\b)",
        text,
        flags=re.IGNORECASE,
    )
    if len(headers) <= 1:
        return {"body": text}

    sections: dict[str, str] = {}
    for block in headers:
        lines = block.strip().split("\n", 1)
        key = lines[0].strip().lower().replace(" ", "_")[:40]
        sections[key] = lines[1].strip() if len(lines) > 1 else block.strip()
    return sections
