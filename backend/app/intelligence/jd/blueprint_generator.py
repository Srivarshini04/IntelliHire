"""JD Blueprint Generator — delegates to orchestration pipeline."""

from __future__ import annotations

from app.intelligence.jd.orchestrator import BlueprintGenerationOrchestrator
from app.intelligence.jd.telemetry import BlueprintGenerationMetrics
from app.intelligence.jd.weight_strategy import RoleClassification
from app.schemas.document import Document
from app.schemas.job import RoleBlueprint


async def generate_blueprint(
    document: Document,
    db=None,
) -> tuple[RoleBlueprint, RoleClassification, BlueprintGenerationMetrics]:
    return await BlueprintGenerationOrchestrator.run(document, db=db)
