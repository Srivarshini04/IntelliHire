"""JD Parser — extract a role blueprint (skills + weights) from pasted JD text.

The skills drive role-gap risk and the fit score, so they must reflect what the
JD actually asks for. Extraction is LLM-first (handles arbitrary prose) with a
deterministic list parser as the offline/failure fallback. Only if both yield
nothing do we fall back to the legacy default so a job still gets created.
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field

from app.llm.factory import get_llm_provider
from app.schemas.fields import ExtractedField, SkillField
from app.schemas.job import RoleBlueprint
from app.skills.normalizer import normalize_skills

logger = logging.getLogger(__name__)

_DEFAULT_WEIGHTS = {
    "technical": 0.35,
    "execution": 0.25,
    "ownership": 0.20,
    "learning": 0.20,
}

# Words that surround skills in prose JDs ("basic knowledge of DSA" -> "DSA").
_FILLER = {
    "software", "developer", "engineer", "with", "skills", "skill", "like",
    "basic", "good", "strong", "solid", "knowledge", "of", "experience",
    "experienced", "in", "the", "a", "an", "and", "or", "proficient",
    "proficiency", "familiarity", "familiar", "expertise", "expert", "such",
    "as", "including", "include", "includes", "working", "hands", "on",
    "understanding", "plus", "preferred", "required", "must", "have", "using",
    "use", "for", "to", "build", "we", "are", "looking",
}


class _SkillList(BaseModel):
    skills: list[str] = Field(default_factory=list)


def _deterministic_skills(description: str) -> list[str]:
    """Pull an explicit, comma/and-separated skill list out of the JD text."""
    if not description:
        return []
    text = re.sub(r"\s+(?:and|&|or)\s+", ", ", description, flags=re.I)
    text = re.sub(r"[/;\n]+", ", ", text)

    skills: list[str] = []
    for fragment in text.split(","):
        words = re.findall(r"[A-Za-z0-9+#.]+", fragment)
        while words and words[0].lower() in _FILLER:
            words.pop(0)
        while words and words[-1].lower() in _FILLER:
            words.pop()
        if not words or len(words) > 4:
            continue
        candidate = " ".join(words).strip(" .")
        if candidate and candidate.lower() not in _FILLER:
            skills.append(candidate)
    return skills


async def _llm_skills(title: str, description: str) -> list[str]:
    provider = get_llm_provider()
    prompt = (
        "Extract the technical skills, tools, programming languages and "
        "frameworks this job requires. Return strictly JSON of the form "
        '{\"skills\": [\"...\"]} with short canonical skill names, no duplicates, '
        "no sentences.\n\n"
        f"Job title: {title}\n\nJob description:\n{description}"
    )
    result = await provider.generate_json(prompt, _SkillList)
    return [s.strip() for s in result.skills if s and s.strip()]


def _skills_to_fields(raw_skills: list[str]) -> list[SkillField]:
    return [
        SkillField(
            name=skill,
            normalized_name=skill.lower(),
            canonical_name=skill,
            confidence=0.7,
        )
        for skill in normalize_skills(raw_skills)
    ]


async def parse_job_description(title: str, description: str) -> RoleBlueprint:
    """Build a role blueprint from the pasted JD, extracting its real skills."""
    raw_skills: list[str] = []
    try:
        raw_skills = await _llm_skills(title, description)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "LLM skill extraction failed (%s); using deterministic parser", exc
        )

    if not raw_skills:
        raw_skills = _deterministic_skills(description)

    if not raw_skills:
        logger.warning("No skills extracted from JD; falling back to legacy defaults")
        raw_skills = ["Python", "LLMs", "FastAPI"]

    return RoleBlueprint(
        role_title=ExtractedField(value=title, confidence=0.5, source=title),
        experience_level=ExtractedField(value="mid", confidence=0.5),
        required_skills=_skills_to_fields(raw_skills),
        behavioral_traits=[
            ExtractedField(value="Ownership", confidence=0.5),
            ExtractedField(value="Execution", confidence=0.5),
            ExtractedField(value="Learning", confidence=0.5),
        ],
        capability_weights=dict(_DEFAULT_WEIGHTS),
        required_evidence=["projects", "github", "production_systems"],
    )
