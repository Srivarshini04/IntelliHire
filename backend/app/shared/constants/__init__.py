"""Shared constants for DELULU v2.

Canonical home for cross-cutting tunables. ``SOURCE_WEIGHTS`` lives here (not in
``confidence_fusion``) so the dependency points the correct direction:
``intelligence`` depends on ``shared``, never the reverse.
"""

from __future__ import annotations

# --- Evidence source trust weights (probability-of-support fusion) ------------
# Keys MUST match app.shared.enums.EvidenceSource values.
SOURCE_WEIGHTS: dict[str, float] = {
    "resume": 0.60,
    "github": 1.00,
    "linkedin": 0.75,
    "leetcode": 0.95,
    "portfolio": 0.80,
    "kaggle": 0.85,
    "huggingface": 0.85,
    "gitlab": 0.90,
    "redrob": 0.90,
    "manual": 1.00,
}
DEFAULT_SOURCE_WEIGHT: float = 0.55  # for unknown / unlisted sources

# --- Confidence bands (must match app.schemas.fields.ConfidenceLevel logic) ----
CONFIDENCE_GREEN_THRESHOLD: float = 0.85   # > this -> GREEN
CONFIDENCE_YELLOW_THRESHOLD: float = 0.60  # >= this -> YELLOW, else RED

# --- Two-stage ranking funnel (100k -> top 100) -------------------------------
DEFAULT_RETRIEVAL_TOP_K: int = 300  # stage-1 shortlist size handed to reasoning
SUBMISSION_SIZE: int = 100          # challenge: exactly 100 ranked rows

__all__ = [
    "SOURCE_WEIGHTS",
    "DEFAULT_SOURCE_WEIGHT",
    "CONFIDENCE_GREEN_THRESHOLD",
    "CONFIDENCE_YELLOW_THRESHOLD",
    "DEFAULT_RETRIEVAL_TOP_K",
    "SUBMISSION_SIZE",
]
