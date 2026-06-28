"""Deterministic RoleDNA provider — enriches an existing RoleBlueprint into RoleDNA.

This is NOT another LLM parser. It reuses the structured fields already extracted
by the Job Intelligence pipeline (RoleBlueprint) and infers higher-level semantic
expectations deterministically. Implements the frozen ``RoleDNAProvider`` protocol
(app.shared.interfaces.RoleDNAProvider).

Decision A: the four semantic fields not present on the frozen RoleDNA contract
(leadership_expectation, success_profile, interview_focus, risk_tolerance) are
stored in ``RoleDNA.metadata`` — the shared contract is NOT modified.
"""

from __future__ import annotations

import logging
from typing import Any

from app.intelligence.role_dna import inference as inf
from app.shared.enums import Intensity
from app.shared.models import RoleDNA

logger = logging.getLogger(__name__)


class BlueprintRoleDNAProvider:
    """Build RoleDNA from a RoleBlueprint dict (preferred) or raw JD text (fallback).

    Input:  job_id, optional jd_text, optional RoleBlueprint dict.
    Output: RoleDNA (id = ``roledna:{job_id}``).
    Responsibility: deterministic enrichment only — no candidate data, no LLM.
    """

    async def build(
        self,
        job_id: str,
        jd_text: str | None = None,
        blueprint: dict[str, Any] | None = None,
    ) -> RoleDNA:
        if blueprint:
            logger.debug("Building RoleDNA for job %s from blueprint", job_id)
            return self._from_blueprint(job_id, blueprint)
        if jd_text:
            logger.debug("Building RoleDNA for job %s from JD text (minimal)", job_id)
            return self._from_jd_text(job_id, jd_text)
        return self._minimal(job_id, "(no blueprint or JD text provided)")

    # --- primary path: enrich the structured blueprint ---
    def _from_blueprint(self, job_id: str, bp: dict[str, Any]) -> RoleDNA:
        role_title = inf.field_value(bp.get("role_title"))
        experience_level = inf.field_value(bp.get("experience_level"))
        domain = inf.field_value(bp.get("domain"))
        must_have = inf.value_list(bp.get("required_skills"))
        nice_to_have = inf.value_list(bp.get("preferred_skills"))
        responsibilities = inf.value_list(bp.get("responsibilities"))
        behavioural = inf.value_list(bp.get("behavioral_traits"))
        success_metrics = inf.value_list(bp.get("success_metrics"))
        capability_weights = dict(bp.get("capability_weights") or {})
        required_evidence = inf.map_required_evidence([str(v) for v in (bp.get("required_evidence") or [])])

        bp_version = None
        versioning = bp.get("versioning")
        if isinstance(versioning, dict):
            bp_version = versioning.get("blueprint_version")

        level = inf.normalize_engineering_level(experience_level if isinstance(experience_level, str) else None)
        floor = inf.seniority_floor(level)
        signal = " ".join(responsibilities + behavioural + success_metrics + must_have).lower()

        ownership = inf.infer_intensity(signal, "ownership", floor=floor)
        learning = inf.infer_intensity(signal, "learning")
        collaboration = inf.infer_intensity(signal, "collaboration", floor=Intensity.MEDIUM)
        research = inf.infer_intensity(signal, "research", floor=Intensity.NONE)
        delivery = inf.infer_intensity(signal, "delivery", floor=Intensity.MEDIUM)
        architecture = inf.max_intensity(
            inf.infer_intensity(signal, "architecture"),
            inf.weights_architecture_floor(capability_weights),
        )
        communication = inf.infer_intensity(signal, "communication", floor=floor)
        ambiguity = inf.infer_intensity(signal, "ambiguity")
        leadership = inf.infer_intensity(signal, "leadership", floor=Intensity.NONE)

        key_dims = {
            "ownership": ownership, "architecture": architecture, "research": research,
            "leadership": leadership, "communication": communication, "delivery": delivery,
        }

        return RoleDNA(
            role_dna_id=f"roledna:{job_id}",
            job_id=job_id,
            role_summary=inf.synthesize_summary(
                role_title if isinstance(role_title, str) else None,
                level,
                domain if isinstance(domain, str) else None,
                must_have,
                responsibilities,
            ),
            must_have_skills=must_have,
            nice_to_have_skills=nice_to_have,
            domain=domain if isinstance(domain, str) else None,
            engineering_level=level,
            ownership_level=ownership,
            ambiguity_tolerance=ambiguity,
            communication_need=communication,
            learning_requirement=learning,
            research_requirement=research,
            collaboration_requirement=collaboration,
            delivery_expectation=delivery,
            system_design_expectation=architecture,
            coding_requirement=Intensity.HIGH,
            culture=behavioural,
            red_flags=[],
            growth_path=None,
            capability_weights=capability_weights,
            required_evidence=required_evidence,
            derived_from_blueprint_version=bp_version,
            metadata={
                "derived": True,
                "source": "blueprint",
                # Decision A — non-frozen semantics live in metadata:
                "leadership_expectation": leadership.value,
                "risk_tolerance": inf.risk_tolerance(level, ambiguity).value,
                "success_profile": inf.synthesize_success_profile(must_have, key_dims),
                "interview_focus": inf.build_interview_focus(must_have, key_dims),
            },
        )

    # --- fallback: minimal enrichment from raw JD text (no re-parsing) ---
    def _from_jd_text(self, job_id: str, jd_text: str) -> RoleDNA:
        signal = jd_text.lower()
        summary = (jd_text.strip().splitlines() or ["(role summary unavailable)"])[0][:280]
        return RoleDNA(
            role_dna_id=f"roledna:{job_id}",
            job_id=job_id,
            role_summary=summary or "(role summary unavailable)",
            ownership_level=inf.infer_intensity(signal, "ownership"),
            learning_requirement=inf.infer_intensity(signal, "learning"),
            collaboration_requirement=inf.infer_intensity(signal, "collaboration", floor=Intensity.MEDIUM),
            research_requirement=inf.infer_intensity(signal, "research", floor=Intensity.NONE),
            delivery_expectation=inf.infer_intensity(signal, "delivery", floor=Intensity.MEDIUM),
            system_design_expectation=inf.infer_intensity(signal, "architecture"),
            communication_need=inf.infer_intensity(signal, "communication"),
            metadata={"derived": True, "source": "jd_text", "note": "minimal enrichment; blueprint preferred"},
        )

    def _minimal(self, job_id: str, note: str) -> RoleDNA:
        return RoleDNA(
            role_dna_id=f"roledna:{job_id}",
            job_id=job_id,
            role_summary=note,
            metadata={"derived": False, "source": "none"},
        )
