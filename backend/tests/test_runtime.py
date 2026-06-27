import asyncio

from app.intelligence.base_orchestrator import BaseDocumentOrchestrator
from app.intelligence.prompt_registry import PromptRegistry, PromptSpec
from app.intelligence.stage_registry import StageRegistry
from app.schemas.document import Document, DocumentQuality


class RuntimeOrchestrator(BaseDocumentOrchestrator[dict]):
    async def extract(self, document, sections, telemetry):
        return {"title": document.filename, "sections": sections}

    def validate(self, result, telemetry):
        telemetry.average_confidence = 0.88

    async def persist(self, document, result, telemetry):
        telemetry.artifact_count += 1


def _doc():
    return Document(
        filename="runtime.pdf",
        filetype="pdf",
        original_text="Role Summary\nBackend Engineer",
        raw_text="Role Summary\nBackend Engineer",
        cleaned_text="Role Summary\nBackend Engineer",
        quality=DocumentQuality(score=90),
    )


def test_stage_registry_supports_dynamic_stage_injection():
    registry = StageRegistry()
    orchestrator = RuntimeOrchestrator(registry=registry)
    orchestrator.pipeline = [
        "quality",
        "sections",
        "normalize",
        "extract",
        "capability_analysis",
        "validate",
        "persist",
    ]

    def capability_stage(ctx):
        ctx.metadata["capability"] = {"technical": 0.8}

    registry.register("capability_analysis", capability_stage)

    result, telemetry = asyncio.run(orchestrator.run(_doc()))
    assert result["title"] == "runtime.pdf"
    assert "capability_analysis" in telemetry.stage_timings_ms


def test_prompt_registry_versions_and_selection():
    registry = PromptRegistry()
    registry.register(
        PromptSpec(
            name="jd_blueprint",
            version="v1",
            provider="gemini",
            model="gemini-2.0-flash",
            temperature=0.1,
            template="Extract JD as JSON",
            output_schema="RoleBlueprint",
        )
    )
    registry.register(
        PromptSpec(
            name="jd_blueprint",
            version="v2",
            provider="gemini",
            model="gemini-2.0-flash",
            temperature=0.0,
            template="Extract JD as strict JSON",
            output_schema="RoleBlueprint",
        )
    )

    latest = registry.get("jd_blueprint")
    assert latest.version == "v2"
    assert "v1" in registry.list("jd_blueprint")["jd_blueprint"]


def test_telemetry_token_and_cost_fields_available():
    _, telemetry = asyncio.run(RuntimeOrchestrator().run(_doc()))
    assert telemetry.input_tokens == 0
    assert telemetry.output_tokens == 0
    assert telemetry.cached_tokens == 0
    assert telemetry.usd_cost == 0.0
