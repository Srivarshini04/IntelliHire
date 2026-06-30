"""DELULU v2 candidate-evaluation runtime + orchestration."""

from __future__ import annotations

from app.runtime.candidate_evaluation_pipeline import (
    CandidateEvaluationPipeline,
    PipelineError,
)
from app.runtime.pipeline_runtime import PipelineRuntime, StageError
from app.runtime.deterministic_ranking_engine import DeterministicRankingEngine
from app.runtime.ranking_orchestrator import RankingOrchestrator
from app.runtime.stage import Stage, StageInputError
from app.runtime.stages import (
    DecisionStage,
    EvidenceStage,
    FusionStage,
    GraphStage,
    ReasoningStage,
)

__all__ = [
    # runtime primitives
    "Stage",
    "StageInputError",
    "PipelineRuntime",
    "StageError",
    # stage adapters
    "EvidenceStage",
    "GraphStage",
    "FusionStage",
    "ReasoningStage",
    "DecisionStage",
    # orchestration
    "CandidateEvaluationPipeline",
    "PipelineError",
    "RankingOrchestrator",
    "DeterministicRankingEngine",
]
