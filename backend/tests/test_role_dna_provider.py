"""Unit tests — deterministic RoleBlueprint -> RoleDNA enrichment."""

from __future__ import annotations

import asyncio

from app.intelligence.role_dna import BlueprintRoleDNAProvider
from app.intelligence.role_dna import inference as inf
from app.shared.enums import EvidenceSource, Intensity
from app.shared.interfaces import RoleDNAProvider
from app.shared.models import RoleDNA

run = asyncio.run


def _bp(**override):
    bp = {
        "role_title": {"value": "Senior Backend Engineer"},
        "experience_level": {"value": "6+ years"},
        "domain": {"value": "Search"},
        "required_skills": [{"normalized_name": "python"}, {"normalized_name": "fastapi"}],
        "preferred_skills": [{"normalized_name": "kubernetes"}],
        "responsibilities": [
            {"value": "Own and ship production services end-to-end"},
            {"value": "Design scalable distributed systems"},
        ],
        "behavioral_traits": [{"value": "Strong ownership; communicate with stakeholders"}],
        "capability_weights": {"backend": 0.4, "system_design": 0.35, "delivery": 0.25},
        "required_evidence": ["github", "resume", "bogus"],
        "versioning": {"blueprint_version": "2.0.0"},
    }
    bp.update(override)
    return bp


def test_protocol_conformance():
    assert isinstance(BlueprintRoleDNAProvider(), RoleDNAProvider)


def test_engineering_level_inference():
    assert inf.normalize_engineering_level("6+ years") == "senior"
    assert inf.normalize_engineering_level("1 year") == "junior"
    assert inf.normalize_engineering_level("Staff Engineer") == "staff"
    assert inf.normalize_engineering_level("Principal") == "staff"
    assert inf.normalize_engineering_level(None) is None


def test_build_maps_blueprint_fields():
    dna = run(BlueprintRoleDNAProvider().build("J1", blueprint=_bp()))
    assert isinstance(dna, RoleDNA)
    assert dna.role_dna_id == "roledna:J1" and dna.job_id == "J1"
    assert dna.engineering_level == "senior"
    assert dna.must_have_skills == ["python", "fastapi"]
    assert dna.nice_to_have_skills == ["kubernetes"]
    assert dna.domain == "Search"
    assert dna.derived_from_blueprint_version == "2.0.0"


def test_capability_weights_reused_verbatim():
    w = {"backend": 0.4, "system_design": 0.35, "delivery": 0.25}
    dna = run(BlueprintRoleDNAProvider().build("J1", blueprint=_bp(capability_weights=w)))
    assert dna.capability_weights == w


def test_required_evidence_maps_known_only():
    dna = run(BlueprintRoleDNAProvider().build("J1", blueprint=_bp()))
    assert dna.required_evidence == [EvidenceSource.GITHUB, EvidenceSource.RESUME]


def test_intensity_inference():
    dna = run(BlueprintRoleDNAProvider().build("J1", blueprint=_bp()))
    assert dna.system_design_expectation in (Intensity.HIGH, Intensity.CRITICAL)
    assert dna.ownership_level in (Intensity.MEDIUM, Intensity.HIGH, Intensity.CRITICAL)
    assert dna.coding_requirement == Intensity.HIGH


def test_decision_a_fields_live_in_metadata_only():
    dna = run(BlueprintRoleDNAProvider().build("J1", blueprint=_bp()))
    for key in ("leadership_expectation", "risk_tolerance", "success_profile", "interview_focus"):
        assert key in dna.metadata
        assert key not in RoleDNA.model_fields  # frozen contract must NOT have grown the field
    assert isinstance(dna.metadata["interview_focus"], list)


def test_deterministic():
    provider = BlueprintRoleDNAProvider()
    a = run(provider.build("J1", blueprint=_bp()))
    b = run(provider.build("J1", blueprint=_bp()))
    assert a.model_dump() == b.model_dump()


def test_jd_text_fallback():
    dna = run(BlueprintRoleDNAProvider().build("J9", jd_text="Own distributed systems and ship fast."))
    assert dna.role_dna_id == "roledna:J9" and dna.metadata["source"] == "jd_text"
