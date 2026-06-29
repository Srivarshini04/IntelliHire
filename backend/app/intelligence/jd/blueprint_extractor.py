"""Blueprint extraction via LLM — structured JSON only, no prose."""

from __future__ import annotations

import json
from pathlib import Path

from app.intelligence.jd.blueprint_llm_schema import BlueprintLLMOutput
from app.intelligence.jd.role_classifier import RoleClassification
from app.intelligence.jd.weight_strategy import WeightStrategy
from app.llm.factory import get_llm_provider
from app.schemas.document import Document
from app.schemas.sections import DocumentSection

PROMPT_VERSION = "blueprint_extract_v1"
PROMPT_PATH = Path(__file__).resolve().parents[4] / "shared" / "prompt_templates" / "jd_blueprint.txt"


def _load_prompt_template() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text()
    return (
        "Extract a job role blueprint as JSON only. "
        "Separate required_skills from preferred_skills. "
        "Every field needs value, confidence (0-1), and source (verbatim quote). "
        "experience_level: junior|mid|senior|lead|principal. "
        "Do not include capability_weights."
    )


class BlueprintExtractor:
    """Stage: Blueprint Extraction (LLM)."""

    @classmethod
    async def extract(
        cls,
        document: Document,
        sections: list[DocumentSection],
        classification: RoleClassification,
        weight_strategy: WeightStrategy,
    ) -> BlueprintLLMOutput:
        llm = get_llm_provider()
        section_payload = {s.name.value: s.text for s in sections}
        template = _load_prompt_template()

        prompt = f"""{template}

ROLE CLASSIFICATION:
{json.dumps(classification.model_dump(), indent=2)}

DOCUMENT SECTIONS:
{json.dumps(section_payload, indent=2)}

Return valid JSON matching the blueprint schema. No prose. No markdown fences.
"""
        system = (
            "You are a job description parser. Output JSON only. "
            "Never merge required and preferred skills. "
            "Normalize experience_level to: junior, mid, senior, lead, or principal."
        )
        return await llm.generate_json(prompt, BlueprintLLMOutput, system=system, temperature=0.1)
