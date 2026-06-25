from app.knowledge.loader import (
    load_certifications,
    load_education,
    load_industries,
    load_job_families,
    load_skills,
)
from app.skills.normalizer import normalize_skill, normalize_skill_record


def test_ontology_files_load():
    assert load_skills()
    assert load_certifications()
    assert load_education()
    assert load_industries()
    assert load_job_families()


def test_skill_normalization_returns_canonical_name():
    assert normalize_skill("py") == "Python"
    assert normalize_skill("JS") == "JavaScript"


def test_skill_normalization_returns_metadata_record():
    record = normalize_skill_record("k8s", source="Required Skills")
    assert record.skill_id == "SKILL_000005"
    assert record.canonical_name == "Kubernetes"
    assert record.category == "DevOps Platform"
    assert record.source == "Required Skills"


def test_unknown_skill_fallback_record():
    record = normalize_skill_record("some_new_skill")
    assert record.skill_id == "SKILL_UNKNOWN"
    assert record.confidence < 0.9
