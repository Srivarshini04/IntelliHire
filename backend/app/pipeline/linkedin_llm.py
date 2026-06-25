"""LinkedIn extraction via LLM — merges into evidence graph."""

from __future__ import annotations

import json
import logging

import httpx

from app.core.config import get_settings
from app.pipeline.linkedin_extractor import build_linkedin_prompt
from app.pipeline.linkedin_parser import LinkedInExtraction, parse_linkedin_profile

logger = logging.getLogger(__name__)

LABEL_TO_FEATURE_ID: dict[str, str] = {
    "authentication": "authentication",
    "role based access control": "role_based_access_control",
    "rbac": "role_based_access_control",
    "scheduling": "scheduling",
    "caching": "caching",
    "notifications": "notifications",
    "payments": "payments",
    "api design": "api_design",
    "database design": "database_design",
    "ci/cd": "ci_cd",
    "containerization": "containerization",
    "monitoring": "monitoring",
    "aws cloud": "cloud_aws",
    "distributed systems": "distributed_systems",
}


def extract_linkedin(
    profile_text: str,
    jd_skills: list[str],
    jd_capabilities: list[str],
) -> tuple[LinkedInExtraction, str]:
    """LLM extraction with heuristic fallback."""
    settings = get_settings()
    source = "heuristic"

    if settings.openai_api_key and settings.use_llm_linkedin:
        try:
            llm_result = _call_llm(profile_text, jd_skills, jd_capabilities)
            source = "llm"
            logger.info("LinkedIn extracted via LLM (%d experiences)", len(llm_result.experiences))
            llm_result.extraction_source = source
            return llm_result, source
        except Exception as exc:
            logger.warning("LLM LinkedIn extraction failed, using heuristic: %s", exc)

    heuristic = parse_linkedin_profile(profile_text)
    heuristic.extraction_source = source
    return heuristic, source


def _call_llm(profile_text: str, jd_skills: list[str], jd_capabilities: list[str]) -> LinkedInExtraction:
    settings = get_settings()
    prompt = build_linkedin_prompt(jd_skills, jd_capabilities, profile_text)

    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": "You extract engineering evidence from LinkedIn profiles. Return valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            f"{settings.llm_api_base.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

    data = json.loads(content)
    return _llm_json_to_extraction(data)


def _llm_json_to_extraction(data: dict) -> LinkedInExtraction:
    result = LinkedInExtraction()
    experiences = data.get("experiences", data.get("experience", []))
    if isinstance(experiences, dict):
        experiences = [experiences]

    feature_set: set[str] = set()
    skill_claims: set[str] = set()

    for exp in experiences:
        if not isinstance(exp, dict):
            continue
        feats = exp.get("features", [])
        techs = exp.get("technologies", [])
        ev_lines = exp.get("evidence", [])
        scale = exp.get("scale", {})

        for f in feats:
            feature_set.add(f)
            result.feature_evidence.setdefault(f, [])
            result.feature_evidence[f].extend(ev_lines[:3] if ev_lines else [f"Role: {exp.get('project_or_role', '')}"])

        for tech in techs:
            skill_claims.add(str(tech))

        if scale:
            result.scale.update({k: v for k, v in scale.items() if v})

        if exp.get("production") or exp.get("production_experience"):
            result.production = True
        if exp.get("ownership") or exp.get("ownership_level"):
            result.ownership = str(exp.get("ownership") or exp.get("ownership_level"))

        result.experiences.append({
            "project_or_role": exp.get("project_or_role", ""),
            "organization": exp.get("organization", ""),
            "features": feats,
            "evidence": ev_lines,
            "scale": scale,
            "production": exp.get("production", False),
            "confidence": exp.get("confidence", 0),
        })

    result.features = sorted(feature_set)
    result.skill_claims = sorted(skill_claims)
    return result


def linkedin_features_for_graph(extraction: LinkedInExtraction) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Format for evidence graph merge."""
    org_map = {f: ["LinkedIn"] for f in extraction.features}
    return org_map, extraction.feature_evidence
