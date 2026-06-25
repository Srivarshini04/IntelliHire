"""Reusable document orchestrator base for JD/Resume pipelines."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from app.documents.chunker import detect_sections
from app.intelligence.telemetry import OrchestratorTelemetry
from app.schemas.document import Document

TResult = TypeVar("TResult")


class BaseDocumentOrchestrator(ABC, Generic[TResult]):
    """Shared orchestration stages with overridable extraction hooks."""

    max_retries: int = 2

    async def run(self, document: Document) -> tuple[TResult, OrchestratorTelemetry]:
        telemetry = OrchestratorTelemetry(document_id=str(document.id), stage="run")
        started = time.perf_counter()

        self.quality_check(document, telemetry)

        section_started = time.perf_counter()
        sections = self.section_detection(document)
        telemetry.section_count = len(sections)
        telemetry.section_detection_ms = round((time.perf_counter() - section_started) * 1000, 2)

        normalize_started = time.perf_counter()
        normalized_sections = self.normalize(sections)
        telemetry.normalization_ms = round((time.perf_counter() - normalize_started) * 1000, 2)

        extract_started = time.perf_counter()
        result = await self._extract_with_retry(document, normalized_sections, telemetry)
        telemetry.extraction_ms = round((time.perf_counter() - extract_started) * 1000, 2)

        validate_started = time.perf_counter()
        self.validate(result, telemetry)
        telemetry.validation_ms = round((time.perf_counter() - validate_started) * 1000, 2)

        persist_started = time.perf_counter()
        await self.persist(document, result, telemetry)
        telemetry.persistence_ms = round((time.perf_counter() - persist_started) * 1000, 2)

        telemetry.processing_time_ms = round((time.perf_counter() - started) * 1000, 2)
        return result, telemetry

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

    async def _extract_with_retry(
        self,
        document: Document,
        sections: dict[str, str],
        telemetry: OrchestratorTelemetry,
    ) -> TResult:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                telemetry.retry_count = attempt
                return await self.extract(document, sections, telemetry)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                telemetry.errors.append(f"extract_attempt_{attempt}: {exc}")
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
