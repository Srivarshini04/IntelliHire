"""Confidence fusion using weighted multi-source evidence."""

from __future__ import annotations

# Canonical weights live in the shared foundation (single source of truth).
from app.shared.constants import DEFAULT_SOURCE_WEIGHT, SOURCE_WEIGHTS


def fuse_confidence(evidence: list[tuple[str, float]]) -> float:
    """
    Probability-of-support fusion:
    final = 1 - Π(1 - weight * confidence)
    """
    if not evidence:
        return 0.0

    remaining = 1.0
    for source, confidence in evidence:
        weight = SOURCE_WEIGHTS.get(source.lower(), DEFAULT_SOURCE_WEIGHT)
        support = max(0.0, min(1.0, weight * confidence))
        remaining *= 1.0 - support

    return round(1.0 - remaining, 4)
