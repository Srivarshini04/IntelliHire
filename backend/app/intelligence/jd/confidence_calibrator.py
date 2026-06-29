"""Confidence calibration — combine multiple signals, don't trust LLM alone."""

from __future__ import annotations

from app.intelligence.jd.blueprint_llm_schema import BlueprintLLMOutput, LLMField, LLMSkillField
from app.intelligence.jd.weight_strategy import RoleClassification, WeightStrategy, select_weight_strategy
from app.schemas.document import Document
from app.schemas.fields import ExtractedField, ExtractionProvenance, SkillField, SourceSpan, VersioningMeta
from app.schemas.job import RoleBlueprint
from app.schemas.sections import DocumentSection
from app.skills.normalizer import normalize_skill

PARSER_VERSION = "1.0.0"


class ConfidenceCalibrator:
    """Stage: Confidence Calibration."""

    @classmethod
    def calibrate_field(
        cls,
        llm_confidence: float,
        section_quality: float,
        document_quality: float,
        validation_score: float = 1.0,
    ) -> float:
        """
        final = weighted blend of LLM confidence + section + document + validation
        """
        final = (
            llm_confidence * 0.45
            + section_quality * 0.20
            + (document_quality / 100.0) * 0.20
            + validation_score * 0.15
        )
        return round(min(max(final, 0.0), 1.0), 3)

    @classmethod
    def _section_quality_for_source(cls, source: str | None, sections: list[DocumentSection]) -> float:
        if not source:
            return 0.5
        for section in sections:
            if source.lower() in section.text.lower():
                return section.confidence
        return 0.6

    @classmethod
    def to_role_blueprint(
        cls,
        output: BlueprintLLMOutput,
        document: Document,
        sections: list[DocumentSection],
        classification: RoleClassification,
        weight_strategy: WeightStrategy,
        *,
        llm_model: str,
        prompt_version: str,
        validation_score: float = 1.0,
    ) -> RoleBlueprint:
        doc_q = document.quality.score

        def map_field(field: LLMField, field_name: str) -> ExtractedField[str]:
            sec_q = cls._section_quality_for_source(field.source, sections)
            conf = cls.calibrate_field(field.confidence, sec_q, doc_q, validation_score)
            span = cls._find_source_span(field.source, document.cleaned_text)
            return ExtractedField(
                value=field.value,
                confidence=conf,
                source=field.source,
                source_span=span,
                provenance=ExtractionProvenance(
                    field=field_name,
                    model=llm_model,
                    prompt_version=prompt_version,
                    parser_version=PARSER_VERSION,
                ),
            )

        def map_skill(skill: LLMSkillField) -> SkillField:
            normalized = normalize_skill(skill.name)
            sec_q = cls._section_quality_for_source(skill.source, sections)
            conf = cls.calibrate_field(skill.confidence, sec_q, doc_q, validation_score)
            return SkillField(
                name=skill.name,
                normalized_name=normalized,
                confidence=conf,
                source=skill.source,
                source_span=cls._find_source_span(skill.source, document.cleaned_text),
                category=skill.category,
                provenance=ExtractionProvenance(
                    field="skill",
                    model=llm_model,
                    prompt_version=prompt_version,
                    parser_version=PARSER_VERSION,
                ),
            )

        domain_field = None
        if output.domain:
            domain_field = map_field(output.domain, "domain")
        elif classification.domain:
            domain_field = ExtractedField(
                value=classification.domain,
                confidence=classification.confidence,
                source="role_classifier",
            )

        industry_field = map_field(output.industry, "industry") if output.industry else None
        employment_field = map_field(output.employment_type, "employment_type") if output.employment_type else None

        return RoleBlueprint(
            role_title=map_field(output.role_title, "role_title"),
            experience_level=map_field(output.experience_level, "experience_level"),
            employment_type=employment_field,
            required_skills=[map_skill(s) for s in output.required_skills],
            preferred_skills=[map_skill(s) for s in output.preferred_skills],
            responsibilities=[map_field(r, "responsibilities") for r in output.responsibilities],
            behavioral_traits=[map_field(t, "behavioral_traits") for t in output.behavioral_traits],
            education=[map_field(e, "education") for e in output.education],
            certifications=[map_field(c, "certifications") for c in output.certifications],
            domain=domain_field,
            industry=industry_field,
            tools=[map_skill(t) for t in output.tools],
            success_metrics=[map_field(m, "success_metrics") for m in output.success_metrics],
            capability_weights=weight_strategy.get_weights(),
            required_evidence=output.required_evidence or ["projects", "github"],
            versioning=VersioningMeta(
                blueprint_version="1.0.0",
                parser_version=PARSER_VERSION,
                prompt_version=prompt_version,
                llm_model=llm_model,
            ),
        )

    @staticmethod
    def _find_source_span(source: str | None, text: str) -> SourceSpan | None:
        if not source or not text:
            return None
        idx = text.lower().find(source.lower()[: min(40, len(source))])
        if idx < 0:
            return None
        end = min(idx + len(source), len(text))
        return SourceSpan(text=source, start_char=idx, end_char=end, page=None)

    @classmethod
    def average_confidence(cls, blueprint: RoleBlueprint) -> float:
        scores = [blueprint.role_title.confidence, blueprint.experience_level.confidence]
        scores.extend(s.confidence for s in blueprint.required_skills)
        return round(sum(scores) / max(len(scores), 1), 3)
