"""Role classification before blueprint extraction."""

from __future__ import annotations

import json
import re

from app.intelligence.jd.weight_strategy import RoleClassification
from app.llm.factory import get_llm_provider
from app.schemas.sections import DocumentSection


SENIORITY_PATTERNS = [
    (r"(?i)\b(principal|staff|distinguished)\b", "principal"),
    (r"(?i)\b(lead|head)\b", "lead"),
    (r"(?i)\b(senior|sr\.?)\b", "senior"),
    (r"(?i)\b(junior|jr\.?|entry[\s-]?level)\b", "junior"),
    (r"(?i)\b(mid[\s-]?level)\b", "mid"),
]

FAMILY_KEYWORDS: dict[str, list[str]] = {
    "backend": ["backend", "api", "server", "fastapi", "django", "microservices"],
    "frontend": ["frontend", "react", "vue", "angular", "ui", "ux engineer"],
    "fullstack": ["full stack", "fullstack", "full-stack"],
    "data_science": ["data scientist", "machine learning", "ml engineer", "ai engineer"],
    "devops": ["devops", "sre", "platform", "infrastructure", "kubernetes"],
    "product": ["product manager", "product owner"],
    "design": ["designer", "ux designer", "ui designer"],
}


class RoleClassifier:
    """Classify role domain/family/seniority to drive prompts and weight strategy."""

    PROMPT_VERSION = "role_classify_v1"

    @classmethod
    def classify_heuristic(cls, sections: list[DocumentSection]) -> RoleClassification:
        combined = " ".join(s.text for s in sections[:3]).lower()
        title_section = next((s.text for s in sections if s.name.value == "role_summary"), combined)

        seniority = "mid"
        for pattern, level in SENIORITY_PATTERNS:
            if re.search(pattern, title_section):
                seniority = level
                break

        family = "backend"
        for fam, keywords in FAMILY_KEYWORDS.items():
            if any(kw in combined for kw in keywords):
                family = fam
                break

        domain = "Software Engineering"
        if family in ("data_science",):
            domain = "Data & AI"
        elif family in ("devops",):
            domain = "Infrastructure"
        elif family in ("product",):
            domain = "Product"
        elif family in ("design",):
            domain = "Design"

        return RoleClassification(
            domain=domain,
            family=family.replace("_", " ").title(),
            specialization=cls._infer_specialization(combined, family),
            seniority=seniority,
            confidence=0.75,
        )

    @classmethod
    async def classify(cls, sections: list[DocumentSection]) -> RoleClassification:
        """LLM classification with heuristic fallback."""
        heuristic = cls.classify_heuristic(sections)
        section_payload = {s.name.value: s.text[:800] for s in sections}

        try:
            llm = get_llm_provider()
            prompt = (
                "Classify this job role. Return JSON only with keys: "
                "domain, family, specialization, seniority, confidence.\n"
                f"seniority must be one of: junior, mid, senior, lead, principal\n"
                f"sections: {json.dumps(section_payload)}"
            )
            raw = await llm.generate_text(prompt, temperature=0.0)
            data = json.loads(raw)
            return RoleClassification(
                domain=data.get("domain", heuristic.domain),
                family=data.get("family", heuristic.family),
                specialization=data.get("specialization", heuristic.specialization),
                seniority=data.get("seniority", heuristic.seniority),
                confidence=float(data.get("confidence", 0.85)),
            )
        except Exception:
            return heuristic

    @staticmethod
    def _infer_specialization(text: str, family: str) -> str:
        if "machine learning" in text or "ml " in text:
            return "Machine Learning"
        if "infrastructure" in text:
            return "Infrastructure"
        if family == "backend":
            return "Backend Services"
        return ""
