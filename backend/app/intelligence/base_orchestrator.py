"""Reusable document orchestrator base for JD/Resume pipelines."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from app.documents.chunker import detect_sections
from app.intelligence.pipeline_context import PipelineContext
from app.intelligence.stage_registry import StageRegistry
from app.intelligence.telemetry import OrchestratorTelemetry
from app.schemas.document import Document

TResult = TypeVar("TResult")


class BaseDocumentOrchestrator(ABC, Generic[TResult]):
    """Shared orchestration stages with overridable extraction hooks."""

    max_retries: int = 2
    pipeline: list[str] = [
        "quality",
        "sections",
        "normalize",
        "extract",
        "validate",
        "persist",
    ]

    def __init__(self, registry: StageRegistry | None = None) -> None:
        self.registry = registry or StageRegistry()
        self._register_default_stages()

    async def run(self, document: Document) -> tuple[TResult, OrchestratorTelemetry]:
        self._ensure_runtime()
        telemetry = OrchestratorTelemetry(document_id=str(document.id), stage="run")
        started = time.perf_counter()
        context = PipelineContext(document=document, telemetry=telemetry)

        for stage_name in self.pipeline:
            stage_started = time.perf_counter()
            await self.registry.execute(stage_name, context)
            telemetry.stage_timings_ms[stage_name] = round(
                (time.perf_counter() - stage_started) * 1000, 2
            )

        telemetry.processing_time_ms = round((time.perf_counter() - started) * 1000, 2)
        result = context.metadata.get("result")
        if result is None:
            raise RuntimeError("Pipeline completed without a result")
        return result, telemetry

    def _ensure_runtime(self) -> None:
        if not hasattr(self, "registry"):
            self.registry = StageRegistry()
            self._register_default_stages()

    def _register_default_stages(self) -> None:
        defaults = {
            "quality": self._stage_quality,
            "sections": self._stage_sections,
            "normalize": self._stage_normalize,
            "extract": self._stage_extract,
            "validate": self._stage_validate,
            "persist": self._stage_persist,
        }
        for name, fn in defaults.items():
            if not self.registry.has(name):
                self.registry.register(name, fn)

    async def _stage_quality(self, context: PipelineContext) -> None:
        self.quality_check(context.document, context.telemetry)
        context.warnings.extend(context.telemetry.warnings)

    async def _stage_sections(self, context: PipelineContext) -> None:
        section_started = time.perf_counter()
        context.sections = self.section_detection(context.document)
        context.telemetry.section_count = len(context.sections)
        context.telemetry.section_detection_ms = round(
            (time.perf_counter() - section_started) * 1000, 2
        )

    async def _stage_normalize(self, context: PipelineContext) -> None:
        normalize_started = time.perf_counter()
        context.sections = self.normalize(context.sections)
        context.telemetry.normalization_ms = round(
            (time.perf_counter() - normalize_started) * 1000, 2
        )

    async def _stage_extract(self, context: PipelineContext) -> None:
        extract_started = time.perf_counter()
        context.metadata["result"] = await self._extract_with_retry(context)
        context.telemetry.extraction_ms = round(
            (time.perf_counter() - extract_started) * 1000, 2
        )

    async def _stage_validate(self, context: PipelineContext) -> None:
        validate_started = time.perf_counter()
        result = context.metadata.get("result")
        self.validate(result, context.telemetry)
        context.telemetry.validation_ms = round(
            (time.perf_counter() - validate_started) * 1000, 2
        )

    async def _stage_persist(self, context: PipelineContext) -> None:
        persist_started = time.perf_counter()
        result = context.metadata.get("result")
        await self.persist(context.document, result, context.telemetry)
        context.telemetry.persistence_ms = round(
            (time.perf_counter() - persist_started) * 1000, 2
        )

    def quality_check(self, document: Document, telemetry: OrchestratorTelemetry) -> None:
        telemetry.document_quality = document.quality.score
        if document.quality.score < 40:
            telemetry.warnings.append(
                f"Low document quality: {document.quality.score}/100"
            )

    def section_detection(self, document: Document) -> dict[str, str]:
        sections = detect_sections(document.cleaned_text)
        document.sections = sections
        return sections

    def normalize(self, sections: dict[str, str]) -> dict[str, str]:
        return sections

    async def _extract_with_retry(self, context: PipelineContext) -> TResult:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                context.telemetry.retry_count = attempt
                return await self.extract(
                    context.document,
                    context.sections,
                    context.telemetry,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                context.telemetry.errors.append(f"extract_attempt_{attempt}: {exc}")
        raise RuntimeError("Extraction failed after retries") from last_error

    @abstractmethod
    async def extract(
        self,
        document: Document,
        sections: dict[str, str],
        telemetry: OrchestratorTelemetry,
    ) -> TResult:
        ...

    @abstractmethod
    def validate(self, result: TResult, telemetry: OrchestratorTelemetry) -> None:
        ...

    @abstractmethod
    async def persist(
        self,
        document: Document,
        result: TResult,
        telemetry: OrchestratorTelemetry,
    ) -> None:
        ...
