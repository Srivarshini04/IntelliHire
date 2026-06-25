"""JD Blueprint Generator using shared orchestration base."""

from __future__ import annotations

from app.intelligence.base_orchestrator import BaseDocumentOrchestrator
from app.intelligence.telemetry import OrchestratorTelemetry
from app.schemas.document import Document
from app.schemas.job import RoleBlueprint


class BlueprintGenerationOrchestrator(BaseDocumentOrchestrator[RoleBlueprint]):
    async def extract(
        self,
        document: Document,
        sections: dict[str, str],
        telemetry: OrchestratorTelemetry,
    ) -> RoleBlueprint:
        raise NotImplementedError("Blueprint extractor implementation pending")

    def validate(self, result: RoleBlueprint, telemetry: OrchestratorTelemetry) -> None:
        telemetry.average_confidence = result.role_title.confidence

    async def persist(
        self,
        document: Document,
        result: RoleBlueprint,
        telemetry: OrchestratorTelemetry,
    ) -> None:
        # No-op to preserve current external behavior.
        return None


async def generate_blueprint(document: Document) -> RoleBlueprint:
    orchestrator = BlueprintGenerationOrchestrator()
    result, _ = await orchestrator.run(document)
    return result
