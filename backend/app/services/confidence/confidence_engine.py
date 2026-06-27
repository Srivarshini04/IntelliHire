"""Confidence Engine — how trustworthy is this candidate's assessment?

Per the DELULU HLD, confidence is driven by three factors:
  - Evidence Quantity:    how many independent sources we have
  - Evidence Quality:     how deep/relevant each source is
  - Cross-source agreement: do the sources corroborate each other?
"""

from collections import Counter


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _source_skill_set(evidence: dict) -> dict[str, set[str]]:
    """Lower-cased skill/keyword sets per source, for cross-source agreement."""
    github = evidence.get("github") or {}
    deep = github.get("deep") or {}
    linkedin = evidence.get("linkedin") or {}
    resume = evidence.get("resume") or {}

    sets: dict[str, set[str]] = {}

    gh = {k.lower() for k in (deep.get("skill_scores") or {}).keys()}
    gh |= {s.lower() for s in (github.get("skills") or {}).get("languages", [])}
    if gh:
        sets["github"] = gh

    li = {s.lower() for s in (linkedin.get("skills") or {}).get("skills", [])}
    li |= {f.lower() for f in (linkedin.get("features") or [])}
    if li:
        sets["linkedin"] = li

    rs = {s.lower() for s in (resume.get("skills") or [])}
    if rs:
        sets["resume"] = rs

    return sets


async def compute_confidence(evidence: dict, capability: dict, role_blueprint: dict) -> dict:
    github = evidence.get("github") or {}
    deep = github.get("deep") or {}
    basic = github.get("basic") or {}
    linkedin = evidence.get("linkedin") or {}
    resume = evidence.get("resume") or {}
    leetcode = github.get("leetcode") or {}
    relevance = evidence.get("relevance") or {}

    # --- Evidence Quantity: independent sources present ---
    has_github = bool(basic.get("repos") or deep.get("candidate_features"))
    has_linkedin = bool(linkedin.get("features") or (linkedin.get("basic") or {}).get("experiences"))
    has_resume = bool(resume.get("skills") or resume.get("profile"))
    has_leetcode = bool(leetcode and not leetcode.get("error"))
    source_count = sum([has_github, has_linkedin, has_resume, has_leetcode])
    # 3+ independent sources saturates quantity confidence.
    quantity = min(source_count / 3.0, 1.0) * 100.0

    # --- Evidence Quality: depth of each present source, scaled by relevance ---
    quality_signals: list[float] = []
    if has_github:
        repos = len(github.get("repositories_analyzed") or []) or len(basic.get("repos") or [])
        feats = len(deep.get("candidate_features") or [])
        quality_signals.append(min(repos * 15.0 + feats * 10.0, 100.0))
    if has_linkedin:
        exp = len((linkedin.get("basic") or {}).get("experiences") or linkedin.get("experiences") or [])
        sk = len((linkedin.get("skills") or {}).get("skills") or [])
        quality_signals.append(min(exp * 20.0 + sk * 5.0, 100.0))
    if has_resume:
        coverage = _num((resume.get("jd_match") or {}).get("coverage"))
        breadth = min(len(resume.get("skills") or []) * 5.0, 60.0)
        quality_signals.append(min(0.6 * coverage + breadth, 100.0))
    quality = sum(quality_signals) / len(quality_signals) if quality_signals else 0.0
    # Irrelevant evidence shouldn't inflate confidence (Relevance Filter output).
    relevance_ratio = relevance.get("relevance_ratio")
    if relevance_ratio is not None:
        quality *= 0.5 + 0.5 * float(relevance_ratio)

    # --- Cross-source agreement: skills corroborated by >= 2 sources ---
    sets = _source_skill_set(evidence)
    if len(sets) >= 2:
        counts: Counter = Counter()
        for skills in sets.values():
            counts.update(skills)
        union = set().union(*sets.values())
        corroborated = sum(1 for v in counts.values() if v >= 2)
        agreement = min((corroborated / max(len(union), 1)) * 200.0, 100.0)
    else:
        # Can't corroborate with a single source — neutral-low.
        agreement = 30.0 if sets else 0.0

    confidence = 0.40 * quantity + 0.35 * quality + 0.25 * agreement

    return {
        "confidence_score": round(confidence, 1),
        "evidence_quantity": round(quantity, 1),
        "evidence_quality": round(quality, 1),
        "cross_source_agreement": round(agreement, 1),
        "source_count": source_count,
    }
