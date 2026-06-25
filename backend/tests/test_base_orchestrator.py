import asyncio

from app.intelligence.base_orchestrator import BaseDocumentOrchestrator
from app.intelligence.telemetry import OrchestratorTelemetry
from app.schemas.document import Document, DocumentQuality


class DummyOrchestrator(BaseDocumentOrchestrator[dict]):
    def __init__(self):
        self.persisted = False

    async def extract(self, document, sections, telemetry):
        return {"sections": sections, "title": document.filename}

    def validate(self, result, telemetry):
        telemetry.average_confidence = 0.9

    async def persist(self, document, result, telemetry):
        self.persisted = True
        telemetry.artifact_count += 1


class RetryOrchestrator(BaseDocumentOrchestrator[dict]):
    def __init__(self):
        self.calls = 0

    async def extract(self, document, sections, telemetry):
        self.calls += 1
        if self.calls < 2:
            raise ValueError("transient")
        return {"ok": True}

    def validate(self, result, telemetry):
        return None

    async def persist(self, document, result, telemetry):
        return None


def _doc(score=80):
    return Document(
        filename="doc.pdf",
        filetype="pdf",
        original_text="Role Summary\nTest",
        raw_text="Role Summary\nTest",
        cleaned_text="Role Summary\nTest",
        quality=DocumentQuality(score=score),
    )


def test_base_orchestrator_runs_all_stages():
    orchestrator = DummyOrchestrator()
    result, telemetry = asyncio.run(orchestrator.run(_doc()))

    assert result["title"] == "doc.pdf"
    assert telemetry.processing_time_ms >= 0
    assert telemetry.section_count >= 1
    assert telemetry.average_confidence == 0.9
    assert orchestrator.persisted is True


def test_base_orchestrator_retries_extract():
    orchestrator = RetryOrchestrator()
    result, telemetry = asyncio.run(orchestrator.run(_doc()))

    assert result["ok"] is True
    assert telemetry.retry_count == 1


def test_quality_warning_is_recorded():
    orchestrator = DummyOrchestrator()
    _, telemetry = asyncio.run(orchestrator.run(_doc(score=20)))

    assert telemetry.warnings
