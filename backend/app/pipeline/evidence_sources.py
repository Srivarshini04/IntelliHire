"""Evidence source reliability — GitHub is evidence; LinkedIn/resume are claims."""

from __future__ import annotations

SOURCE_RELIABILITY: dict[str, float] = {
    "github": 0.95,
    "leetcode": 0.85,
    "hackerrank": 0.80,
    "linkedin": 0.60,
    "resume": 0.50,
    "portfolio": 0.50,  # self-reported, like a resume
}

# Priority order for tie-breaking (highest first)
SOURCE_PRIORITY: list[str] = ["github", "leetcode", "hackerrank", "linkedin", "resume", "portfolio"]


def reliability(source: str) -> float:
    return SOURCE_RELIABILITY.get(source, 0.40)
