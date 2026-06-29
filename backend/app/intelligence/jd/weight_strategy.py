"""Role classification and weight strategy selection."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class RoleClassification(BaseModel):
    domain: str
    family: str
    specialization: str = ""
    seniority: str  # junior | mid | senior | lead | principal
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


class WeightStrategy(ABC):
    """Select capability weights by role family — never hardcode in LLM output."""

    name: str

    @abstractmethod
    def get_weights(self) -> dict[str, float]:
        ...


class BackendEngineerWeights(WeightStrategy):
    name = "backend_engineer"

    def get_weights(self) -> dict[str, float]:
        return {
            "technical": 0.40,
            "execution": 0.25,
            "ownership": 0.20,
            "learning": 0.15,
        }


class DataScientistWeights(WeightStrategy):
    name = "data_scientist"

    def get_weights(self) -> dict[str, float]:
        return {
            "technical": 0.35,
            "execution": 0.20,
            "ownership": 0.15,
            "learning": 0.30,
        }


class DevOpsWeights(WeightStrategy):
    name = "devops"

    def get_weights(self) -> dict[str, float]:
        return {
            "technical": 0.30,
            "execution": 0.35,
            "ownership": 0.25,
            "learning": 0.10,
        }


class MLInfrastructureWeights(WeightStrategy):
    name = "ml_infrastructure"

    def get_weights(self) -> dict[str, float]:
        return {
            "technical": 0.38,
            "execution": 0.27,
            "ownership": 0.20,
            "learning": 0.15,
        }


class ProductManagerWeights(WeightStrategy):
    name = "product_manager"

    def get_weights(self) -> dict[str, float]:
        return {
            "technical": 0.15,
            "execution": 0.30,
            "ownership": 0.35,
            "learning": 0.20,
        }


class DesignerWeights(WeightStrategy):
    name = "designer"

    def get_weights(self) -> dict[str, float]:
        return {
            "technical": 0.20,
            "execution": 0.30,
            "ownership": 0.30,
            "learning": 0.20,
        }


class DefaultWeights(WeightStrategy):
    name = "default"

    def get_weights(self) -> dict[str, float]:
        return {
            "technical": 0.35,
            "execution": 0.25,
            "ownership": 0.20,
            "learning": 0.20,
        }


STRATEGY_REGISTRY: dict[str, WeightStrategy] = {
    "backend": BackendEngineerWeights(),
    "frontend": BackendEngineerWeights(),
    "fullstack": BackendEngineerWeights(),
    "data_science": DataScientistWeights(),
    "data": DataScientistWeights(),
    "devops": DevOpsWeights(),
    "sre": DevOpsWeights(),
    "ml": MLInfrastructureWeights(),
    "machine_learning": MLInfrastructureWeights(),
    "ai": MLInfrastructureWeights(),
    "product": ProductManagerWeights(),
    "design": DesignerWeights(),
    "ux": DesignerWeights(),
}


def select_weight_strategy(classification: RoleClassification) -> WeightStrategy:
    family_key = classification.family.lower().replace(" ", "_")
    spec_key = classification.specialization.lower().replace(" ", "_")

    for key in (spec_key, family_key):
        if key in STRATEGY_REGISTRY:
            return STRATEGY_REGISTRY[key]

    domain = classification.domain.lower()
    if "engineer" in domain or "engineering" in domain:
        return BackendEngineerWeights()
    if "data" in domain:
        return DataScientistWeights()
    if "product" in domain:
        return ProductManagerWeights()

    return DefaultWeights()
