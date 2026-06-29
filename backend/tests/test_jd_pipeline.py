"""Unit tests for JD blueprint pipeline stages (no LLM)."""

from app.documents.service import build_document_from_text
from app.intelligence.jd.business_validator import BlueprintBusinessValidator
from app.intelligence.jd.blueprint_llm_schema import BlueprintLLMOutput, LLMField, LLMSkillField
from app.intelligence.jd.orchestrator import BlueprintGenerationOrchestrator
from app.intelligence.jd.role_classifier import RoleClassifier
from app.intelligence.jd.section_detector import SectionDetector
from app.intelligence.jd.weight_strategy import RoleClassification, select_weight_strategy
from app.skills.normalizer import normalize_skill


SAMPLE_JD = """Senior Backend Engineer

Required Skills
Python, FastAPI, K8s

Preferred Skills
GraphQL

Responsibilities
- Build scalable APIs
- Own service reliability
"""


def test_section_detector_splits_skills():
    doc = build_document_from_text(SAMPLE_JD)
    sections = SectionDetector.detect(doc)
    names = {s.name.value for s in sections}
    assert "required_skills" in names or "responsibilities" in names
    assert len(sections) >= 2


def test_pre_llm_alias_normalization():
    doc = build_document_from_text("Required Skills\nJS, TS, Py, TF, K8s")
    sections = SectionDetector.detect(doc)
    normalized = BlueprintGenerationOrchestrator._normalize_section_aliases(sections)
    combined = " ".join(s.text for s in normalized)
    assert "JavaScript" in combined
    assert "Kubernetes" in combined


def test_role_classifier_heuristic():
    doc = build_document_from_text(SAMPLE_JD)
    sections = SectionDetector.detect(doc)
    classification = RoleClassifier.classify_heuristic(sections)
    assert classification.seniority == "senior"
    assert classification.domain == "Software Engineering"


def test_weight_strategy_selection():
    classification = RoleClassification(
        domain="Software Engineering",
        family="Backend",
        specialization="Machine Learning Infrastructure",
        seniority="senior",
    )
    strategy = select_weight_strategy(classification)
    assert abs(sum(strategy.get_weights().values()) - 1.0) < 0.01


def test_skill_normalizer_aliases():
    assert normalize_skill("JS") == "JavaScript"
    assert normalize_skill("k8s") == "Kubernetes"


def test_business_validator_rejects_empty_required_skills():
    output = BlueprintLLMOutput(
        role_title=LLMField(value="Engineer", confidence=0.9, source="Engineer"),
        experience_level=LLMField(value="senior", confidence=0.9, source="5+ years"),
        required_skills=[],
    )
    classification = RoleClassification(
        domain="Software Engineering",
        family="Backend",
        seniority="senior",
    )
    result = BlueprintBusinessValidator.validate(output, classification)
    assert not result.passed
    assert any("required_skills" in e for e in result.errors)


def test_business_validator_overlap_warning():
    skill = LLMSkillField(name="Python", confidence=0.9, source="Python")
    output = BlueprintLLMOutput(
        role_title=LLMField(value="Engineer", confidence=0.9, source="Engineer"),
        experience_level=LLMField(value="senior", confidence=0.9, source="5+ years"),
        required_skills=[skill],
        preferred_skills=[skill],
    )
    classification = RoleClassification(
        domain="Software Engineering",
        family="Backend",
        seniority="senior",
    )
    result = BlueprintBusinessValidator.validate(output, classification)
    assert result.passed
    assert result.warnings
