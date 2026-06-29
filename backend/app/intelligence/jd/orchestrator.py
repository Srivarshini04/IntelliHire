"""Blueprint generation orchestration pipeline — independently testable stages."""

from __future__ import annotations

import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.artifacts import save_artifact
from app.intelligence.jd.blueprint_extractor import PROMPT_VERSION, BlueprintExtractor
from app.intelligence.jd.business_validator import BlueprintBusinessValidator
from app.intelligence.jd.confidence_calibrator import ConfidenceCalibrator, PARSER_VERSION
from app.intelligence.jd.role_classifier import RoleClassifier
from app.intelligence.jd.schema_validator import SchemaValidationError, validate_with_retry
from app.intelligence.jd.section_detector import SectionDetector
from app.intelligence.jd.telemetry import BlueprintGenerationMetrics
from app.intelligence.jd.weight_strategy import RoleClassification, select_weight_strategy
from app.llm.factory import get_llm_provider
from app.schemas.artifacts import ArtifactType, ArtifactStatus
from app.schemas.document import Document
from app.schemas.job import RoleBlueprint

logger = logging.getLogger(__name__)

MIN_QUALITY_THRESHOLD = 40.0


class BlueprintGenerationError(Exception):
    def __init__(self, message: str, metrics: BlueprintGenerationMetrics):
        super().__init__(message)
        self.metrics = metrics


class BlueprintGenerationOrchestrator:
    """
    Document → Quality → Sections → Classify → Normalize → Extract →
    Validate → Business Rules → Calibrate → Persist
    """

    @classmethod
    async def run(
        cls,
        document: Document,
        db: AsyncSession | None = None,
    ) -> tuple[RoleBlueprint, RoleClassification, BlueprintGenerationMetrics]:
        started = time.perf_counter()
        metrics = BlueprintGenerationMetrics(
            document_id=document.id,
            document_quality=document.quality.score,
            prompt_version=PROMPT_VERSION,
            parser_version=PARSER_VERSION,
        )

        try:
            # Stage 1: Quality check
            cls._quality_check(document, metrics)

            # Stage 2: Section detection
            sections = SectionDetector.detect(document)
            metrics.section_count = len(sections)
            document.sections = SectionDetector.sections_to_dict(sections)

            # Stage 3: Pre-LLM skill alias normalization in section text
            sections = cls._normalize_section_aliases(sections)

            # Stage 4: Role classification
            classification = await RoleClassifier.classify(sections)
            weight_strategy = select_weight_strategy(classification)

            # Stage 5–6: Blueprint extraction with schema validation + retry
            llm = get_llm_provider()
            metrics.llm_model = llm.model_name

            llm_output, retry_count = await validate_with_retry(
                BlueprintExtractor.extract,
                document,
                sections,
                classification,
                weight_strategy,
            )
            metrics.retry_count = retry_count

            # Stage 7: Business validation
            biz_result = BlueprintBusinessValidator.validate(llm_output, classification)
            metrics.validation_warnings.extend(biz_result.warnings)
            if not biz_result.passed:
                metrics.validation_errors.extend(biz_result.errors)
                metrics.status = "failed"
                raise BlueprintGenerationError(
                    f"Business validation failed: {biz_result.errors}",
                    metrics,
                )

            validation_score = 1.0 if not biz_result.warnings else 0.85

            # Stage 8: Confidence calibration + weight strategy
            blueprint = ConfidenceCalibrator.to_role_blueprint(
                llm_output,
                document,
                sections,
                classification,
                weight_strategy,
                llm_model=llm.model_name,
                prompt_version=PROMPT_VERSION,
                validation_score=validation_score,
            )
            metrics.average_confidence = ConfidenceCalibrator.average_confidence(blueprint)

            # Stage 9: Persist artifacts
            if db:
                await cls._persist(db, document, sections, classification, blueprint, metrics)

            metrics.processing_time_ms = round((time.perf_counter() - started) * 1000, 1)
            metrics.status = "draft"
            return blueprint, classification, metrics

        except SchemaValidationError as exc:
            metrics.validation_errors = exc.errors
            metrics.retry_count = exc.attempts
            metrics.status = "failed"
            metrics.processing_time_ms = round((time.perf_counter() - started) * 1000, 1)
            raise BlueprintGenerationError(str(exc), metrics) from exc
        except BlueprintGenerationError:
            metrics.processing_time_ms = round((time.perf_counter() - started) * 1000, 1)
            raise
        except Exception as exc:
            metrics.validation_errors.append(str(exc))
            metrics.status = "failed"
            metrics.processing_time_ms = round((time.perf_counter() - started) * 1000, 1)
            logger.exception("Blueprint generation failed for document %s", document.id)
            raise BlueprintGenerationError(str(exc), metrics) from exc

    @staticmethod
    def _quality_check(document: Document, metrics: BlueprintGenerationMetrics) -> None:
        if document.quality.score < MIN_QUALITY_THRESHOLD:
            metrics.validation_warnings.append(
                f"Document quality {document.quality.score}/100 below threshold — "
                "extraction may be unreliable"
            )

    @staticmethod
    def _normalize_section_aliases(sections):
        """Pre-LLM: expand obvious skill aliases in section text."""
        from app.schemas.sections import DocumentSection

        alias_replacements = {
            r"\bJS\b": "JavaScript",
            r"\bTS\b": "TypeScript",
            r"\bPy\b": "Python",
            r"\bTF\b": "TensorFlow",
            r"\bK8s\b": "Kubernetes",
        }
        import re

        normalized = []
        for section in sections:
            text = section.text
            for pattern, replacement in alias_replacements.items():
                text = re.sub(pattern, replacement, text)
            normalized.append(section.model_copy(update={"text": text}))
        return normalized

    @staticmethod
    async def _persist(
        db: AsyncSession,
        document: Document,
        sections,
        classification: RoleClassification,
        blueprint: RoleBlueprint,
        metrics: BlueprintGenerationMetrics,
    ) -> None:
        document_payload = document.model_dump(mode="json")
        document_payload["sections"] = SectionDetector.sections_to_dict(sections)
        await save_artifact(
            db,
            document.id,
            ArtifactType.EXTRACTED_TEXT,
            document_payload,
            status=ArtifactStatus.DRAFT,
        )
        await save_artifact(
            db,
            document.id,
            ArtifactType.BLUEPRINT_DRAFT,
            blueprint.model_dump(mode="json"),
            status=ArtifactStatus.PENDING_REVIEW,
        )
        await save_artifact(
            db,
            document.id,
            ArtifactType.ROLE_CLASSIFICATION,
            classification.model_dump(mode="json"),
            status=ArtifactStatus.DRAFT,
        )
        await save_artifact(
            db,
            document.id,
            ArtifactType.BLUEPRINT_METRICS,
            metrics.model_dump(mode="json"),
            status=ArtifactStatus.DRAFT,
        )
        await db.commit()
