"""Integrated LeetCode evidence service — first-class provider.

Wraps :class:`app.services.evidence.leetcode_engine.LeetCodeEvaluator` (the
DELULU v2 scoring engine) into the same ``analyze_*_evidence`` shape the
GitHub and LinkedIn providers use, so LeetCode can stand on its own as a
candidate-intelligence source rather than only as a GitHub sub-call.

The evaluator performs blocking ``requests`` calls against LeetCode's GraphQL
API, so it runs in a worker thread. Any failure (private profile, unknown
user, network error) degrades gracefully to ``{"error": ...}`` rather than
breaking the surrounding analysis.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.services.evidence.leetcode_engine import LeetCodeEvaluator

logger = logging.getLogger(__name__)


async def analyze_leetcode_evidence(
    leetcode_url: str,
    role_blueprint: dict | None = None,
) -> dict[str, Any]:
    """Full LeetCode evidence package for the hiring pipeline.

    ``role_blueprint`` is accepted for interface symmetry with the other
    providers; LeetCode scoring is role-agnostic (it measures raw algorithmic
    skill), so it is not currently used to weight the result.
    """
    if not leetcode_url or not leetcode_url.strip():
        return {"source": "leetcode", "leetcode_url": leetcode_url, "error": "No LeetCode URL provided"}

    try:
        result = await asyncio.to_thread(LeetCodeEvaluator.evaluate, leetcode_url)
    except Exception as exc:  # noqa: BLE001 — engine raises ValueError / network errors
        logger.warning("LeetCode evaluation failed for %s: %s", leetcode_url, exc)
        return {"source": "leetcode", "leetcode_url": leetcode_url, "error": str(exc)}

    return {
        "source": "leetcode",
        "leetcode_url": leetcode_url,
        "source_url": leetcode_url,
        **result,
    }
