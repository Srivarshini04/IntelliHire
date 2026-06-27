"""Variant-aware skill matching shared by the pipeline and risk engine.

Required JD skills, resume skills and free text rarely use identical spelling
("Java Script" vs "JavaScript", "Tailwind CSS" vs "Tailwind", "JS" vs
"JavaScript"). Literal matching under-counts real coverage, so matching is done
on a canonical form (case/spacing/punctuation removed) plus a small synonym map.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# Canonical-form synonyms (keys are already canonicalized: lowercased, alnum only).
_SYNONYMS: dict[str, str] = {
    "js": "javascript",
    "ecmascript": "javascript",
    "reactjs": "react",
    "ts": "typescript",
    "py": "python",
    "golang": "go",
    "node": "nodejs",
    "nodejs": "nodejs",
    "postgres": "postgresql",
    "psql": "postgresql",
    "k8s": "kubernetes",
    "tailwind": "tailwindcss",
    "tailwindcss": "tailwindcss",
    "expressjs": "express",
    "nextjs": "next",
    "dsa": "datastructuresandalgorithms",
    "datastructures": "datastructuresandalgorithms",
}


def canonical(skill: str) -> str:
    """Reduce a skill name to a comparable token (no case/space/punctuation)."""
    token = re.sub(r"[^a-z0-9]+", "", skill.lower())
    return _SYNONYMS.get(token, token)


def _variants(required: str) -> set[str]:
    """All spellings of a skill to look for as whole words in free text."""
    canon = canonical(required)
    variants = {required.lower().strip(), canon}
    # Reverse synonyms: every alias that canonicalizes to the same token.
    variants |= {alias for alias, target in _SYNONYMS.items() if target == canon}
    return {v for v in variants if len(v) >= 2}


def matches_skill_list(required: str, candidate_skills: Iterable[str]) -> bool:
    """True if a required skill appears (variant-aware) in a list of skills."""
    canon = canonical(required)
    return any(canonical(s) == canon for s in candidate_skills if s)


def matches_text(required: str, text: str) -> bool:
    """True if a required skill appears as a whole word/phrase in free text."""
    if not text:
        return False
    lowered = text.lower()
    for variant in _variants(required):
        # Allow optional whitespace inside the phrase ("java script" ~ "javascript")
        # and an optional trailing version number ("html" ~ "HTML5", "css" ~ "CSS3").
        body = re.escape(variant).replace(r"\ ", r"\s*")
        pattern = r"(?<![a-z0-9])" + body + r"(?:[0-9]+(?:\.[0-9]+)?)?(?![a-z])"
        if re.search(pattern, lowered):
            return True
    return False


def is_covered(required: str, *, skills: Iterable[str] = (), text: str = "") -> bool:
    """True if a required skill is evidenced by either a skill list or free text."""
    return matches_skill_list(required, skills) or matches_text(required, text)
