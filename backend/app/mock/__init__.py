"""Mock data for DELULU v2 — one coherent candidate (CAND_0004989) for one job
(JOB_BACKEND_1), threaded end-to-end through every shared model.

These JSON fixtures let each developer test their workstream independently. Every
object that maps to a shared model validates against ``app.shared.models`` and
carries ``schema_version`` + its required stable id. Ids are consistent across
files:

    candidate_id = "CAND_0004989"
    job_id       = "JOB_BACKEND_1"
    graph_id     = "graph:CAND_0004989:JOB_BACKEND_1"
    role_dna_id  = "roledna:JOB_BACKEND_1"
    reasoning_id = "reasoning:CAND_0004989:JOB_BACKEND_1"
    decision_id  = "decision:CAND_0004989:JOB_BACKEND_1"
    ranked_list_id = "rankedlist:JOB_BACKEND_1:rerank"

Usage::

    from app.mock import load, load_evidence, load_graph, load_role_dna
    raw = load("mock_candidate")          # -> dict (no shared model for raw candidate)
    evidence = load_evidence()            # -> list[Evidence]
    graph = load_graph()                  # -> CandidateGraph
"""

from __future__ import annotations

import json
from pathlib import Path

from app.shared.models import (
    CandidateGraph,
    CandidateReasoning,
    Evidence,
    HiringDecision,
    RankedList,
    RoleDNA,
)

_DIR = Path(__file__).resolve().parent

CANDIDATE_ID = "CAND_0004989"
JOB_ID = "JOB_BACKEND_1"

# Logical name -> filename (without extension).
_FILES = {
    "mock_candidate": "mock_candidate",
    "mock_job": "mock_job",
    "mock_evidence": "mock_evidence",
    "mock_graph": "mock_graph",
    "mock_reasoning": "mock_reasoning",
    "mock_decision": "mock_decision",
    "mock_ranking": "mock_ranking",
}

__all__ = [
    "CANDIDATE_ID",
    "JOB_ID",
    "load",
    "load_candidate",
    "load_job",
    "load_role_dna",
    "load_evidence",
    "load_graph",
    "load_reasoning",
    "load_decision",
    "load_ranking",
]


def load(name: str) -> dict | list:
    """Load a mock JSON fixture by logical name (e.g. ``"mock_evidence"``).

    Returns the parsed JSON as-is (``dict`` for most files, ``list`` for
    ``mock_evidence``). Accepts names with or without the ``.json`` suffix.
    """
    key = name[:-5] if name.endswith(".json") else name
    stem = _FILES.get(key, key)
    path = _DIR / f"{stem}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Unknown mock fixture {name!r}; known: {sorted(_FILES)}"
        )
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


# --- raw (no shared model) helpers ---------------------------------------


def load_candidate() -> dict:
    """Raw challenge-shaped candidate profile (CAND_0004989)."""
    return load("mock_candidate")  # type: ignore[return-value]


def load_job() -> dict:
    """Raw job dict, including its embedded ``role_dna`` section."""
    return load("mock_job")  # type: ignore[return-value]


# --- typed (shared model) helpers ----------------------------------------


def load_role_dna() -> RoleDNA:
    """The job's RoleDNA section, parsed into the shared model."""
    return RoleDNA.model_validate(load_job()["role_dna"])


def load_evidence() -> list[Evidence]:
    """All Evidence objects for the candidate (includes one contradicts item)."""
    return [Evidence.model_validate(item) for item in load("mock_evidence")]


def load_graph() -> CandidateGraph:
    return CandidateGraph.model_validate(load("mock_graph"))


def load_reasoning() -> CandidateReasoning:
    return CandidateReasoning.model_validate(load("mock_reasoning"))


def load_decision() -> HiringDecision:
    return HiringDecision.model_validate(load("mock_decision"))


def load_ranking() -> RankedList:
    return RankedList.model_validate(load("mock_ranking"))
