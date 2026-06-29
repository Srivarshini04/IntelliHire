"""Business rule validation — outside the LLM."""

from __future__ import annotations

import re

from app.intelligence.jd.blueprint_llm_schema import BlueprintLLMOutput
from app.intelligence.jd.weight_strategy import RoleClassification

VALID_SENIORITY = frozenset({"junior", "mid", "senior", "lead", "principal"})
EXPERIENCE_RANGE_RE = re.compile(r"(\d+)\s*[-–to]+\s*(\d+)|(\d+)\+?\s*years?", re.I)


class BusinessValidationResult:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0


class BlueprintBusinessValidator:
    """Stage: Business Rule Validation."""

    @classmethod
    def validate(
        cls,
        output: BlueprintLLMOutput,
        classification: RoleClassification,
    ) -> BusinessValidationResult:
        result = BusinessValidationResult()

        if not output.role_title.value.strip():
            result.errors.append("role_title is required")

        if not output.required_skills:
            result.errors.append("required_skills must not be empty")

        req_names = {s.name.lower() for s in output.required_skills}
        pref_names = {s.name.lower() for s in output.preferred_skills}
        overlap = req_names & pref_names
        if overlap:
            result.warnings.append(f"skills appear in both required and preferred: {overlap}")

        level = output.experience_level.value.lower().strip()
        if level not in VALID_SENIORITY:
            result.warnings.append(f"experience_level '{level}' not in standard set")

        if not EXPERIENCE_RANGE_RE.search(output.experience_level.source or output.experience_level.value):
            result.warnings.append("experience range not clearly detected in source")

        if classification.domain and output.domain:
            if classification.domain.lower() not in (output.domain.value or "").lower():
                result.warnings.append("domain mismatch between classifier and extraction")

        if not output.responsibilities:
            result.warnings.append("no responsibilities extracted")

        return result
