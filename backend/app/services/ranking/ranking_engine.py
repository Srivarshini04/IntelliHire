"""Ranking Engine — Fit = 0.55×Capability + 0.25×HTI + 0.20×Confidence - 0.15×Risk"""


def compute_fit_score(capability: float, hti: float, confidence: float, risk: float) -> float:
    return 0.55 * capability + 0.25 * hti + 0.20 * confidence - 0.15 * risk


async def rank_candidates(candidates: list[dict]) -> list[dict]:
    ranked = sorted(candidates, key=lambda c: c.get("fit_score", 0), reverse=True)
    for i, candidate in enumerate(ranked, start=1):
        candidate["rank"] = i
    return ranked
