"""Normalize provider packages into standardized :class:`EvidenceObject`s.

Each ``analyze_*_evidence`` provider returns a rich, source-specific dict. The
functions here distil those dicts into the canonical evidence shape so the
pipeline can persist, score and explain every source the same way.

These normalizers are pure and side-effect free — they never raise on partial
or empty packages, which keeps the analysis pipeline resilient when a provider
degrades (missing API token, network failure, private profile).
"""

from __future__ import annotations

from typing import Any

from app.services.evidence.base import EvidenceObject, EvidenceSignal, build_evidence


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def normalize_github(pkg: dict[str, Any]) -> EvidenceObject:
    """GitHub package → evidence. Skills come from detected languages + scores."""
    pkg = pkg or {}
    skills = (pkg.get("skills") or {}).get("languages", [])
    features = pkg.get("features") or []
    repos = pkg.get("repositories_analyzed") or []
    maturity = _num(pkg.get("engineering_maturity"))
    gem = pkg.get("hidden_gem") or {}
    fit = (pkg.get("jd_match") or {}).get("overall_fit")

    signals = [
        EvidenceSignal(label="engineering_maturity", detail=f"Maturity {maturity:.0f}/100", weight=maturity / 100.0),
        EvidenceSignal(label="repositories_analyzed", detail=f"{len(repos)} repos analyzed", value=len(repos)),
    ]
    if features:
        signals.append(
            EvidenceSignal(label="features_detected", detail=", ".join(map(str, features[:8])), value=len(features))
        )
    if gem.get("hidden_gem"):
        signals.append(EvidenceSignal(label="hidden_gem", detail=str(gem.get("reason", "")), weight=1.0))

    summary = f"GitHub: {len(repos)} repos analyzed, {len(features)} production features, maturity {maturity:.0f}/100"
    return build_evidence(
        "github",
        source_url=pkg.get("github_url"),
        relevance_score=_num(fit) if fit is not None else None,
        summary=summary,
        skills=[str(s) for s in skills],
        signals=signals,
        highlights=[str(f) for f in features[:10]],
        raw={"basic": pkg.get("basic"), "repos": pkg.get("repos")},
        processed={
            "capabilities": pkg.get("capabilities", {}),
            "engineering_maturity": maturity,
            "hidden_gem": gem,
            "jd_match": pkg.get("jd_match", {}),
            "leetcode": pkg.get("leetcode"),
        },
    )


def normalize_linkedin(pkg: dict[str, Any]) -> EvidenceObject:
    """LinkedIn package → evidence. Skills merge declared skills + skill claims."""
    pkg = pkg or {}
    skills = (pkg.get("skills") or {}).get("skills", [])
    features = pkg.get("features") or []
    experiences = pkg.get("experiences") or []
    ownership = pkg.get("ownership", "Unknown")
    scale = pkg.get("scale") or {}

    signals = [
        EvidenceSignal(label="ownership", detail=str(ownership)),
        EvidenceSignal(label="experiences", detail=f"{len(experiences)} roles", value=len(experiences)),
    ]
    if pkg.get("production"):
        signals.append(EvidenceSignal(label="production_experience", detail="Shipped to production", weight=1.0))
    if scale:
        signals.append(EvidenceSignal(label="scale", detail=str(scale)))

    summary = f"LinkedIn: {len(experiences)} roles, ownership '{ownership}', {len(features)} claimed features"
    return build_evidence(
        "linkedin",
        source_url=pkg.get("linkedin_url"),
        summary=summary,
        skills=[str(s) for s in skills],
        signals=signals,
        highlights=[str(f) for f in features[:10]],
        raw={"basic": pkg.get("basic")},
        processed={
            "ownership": ownership,
            "production": pkg.get("production", False),
            "scale": scale,
            "experiences": experiences,
            "education": pkg.get("education", []),
        },
        error=(pkg.get("basic") or {}).get("error"),
    )


def normalize_leetcode(pkg: dict[str, Any]) -> EvidenceObject:
    """LeetCode package → evidence. The coding-skill score drives relevance."""
    pkg = pkg or {}
    if pkg.get("error"):
        return build_evidence("leetcode", source_url=pkg.get("source_url"), error=str(pkg["error"]))

    coding = _num(pkg.get("coding_skill"))
    total = int(_num(pkg.get("total_solved")))
    tier = pkg.get("tier", "")
    signals = [
        EvidenceSignal(label="coding_skill", detail=f"{coding:.0f}/100 ({tier})", weight=coding / 100.0),
        EvidenceSignal(
            label="problems_solved",
            detail=f"{total} solved (E{int(_num(pkg.get('easy_solved')))}/"
            f"M{int(_num(pkg.get('medium_solved')))}/H{int(_num(pkg.get('hard_solved')))})",
            value=total,
        ),
    ]
    if pkg.get("contest_rating"):
        signals.append(EvidenceSignal(label="contest_rating", detail=str(int(_num(pkg.get("contest_rating"))))))

    summary = f"LeetCode: {total} problems solved, coding skill {coding:.0f}/100 ({tier})"
    return build_evidence(
        "leetcode",
        source_url=pkg.get("source_url"),
        relevance_score=coding or None,
        summary=summary,
        skills=["Data Structures", "Algorithms"] if total else [],
        signals=signals,
        highlights=list(pkg.get("strengths") or [])[:5],
        raw={"username": pkg.get("username"), "ranking": pkg.get("ranking")},
        processed={
            "tier": tier,
            "scores": {
                k: pkg.get(k)
                for k in ("volume", "mastery", "hard_depth", "balance", "contest_bonus", "coding_skill")
            },
            "coverage": pkg.get("coverage", {}),
            "improvements": pkg.get("improvements", []),
        },
    )


def normalize_resume(pkg: dict[str, Any]) -> EvidenceObject:
    """Resume package (profile + jd_match) → evidence."""
    pkg = pkg or {}
    skills = pkg.get("skills") or []
    jd_match = pkg.get("jd_match") or {}
    coverage = _num(jd_match.get("coverage"))
    matched = jd_match.get("matched") or []
    profile = pkg.get("profile") or {}
    name = (profile.get("name") or {}).get("value") if isinstance(profile.get("name"), dict) else None

    signals = [
        EvidenceSignal(label="skills_claimed", detail=f"{len(skills)} skills", value=len(skills)),
        EvidenceSignal(label="jd_coverage", detail=f"{coverage:.0f}% of required skills", weight=coverage / 100.0),
    ]
    summary = f"Resume{f' for {name}' if name else ''}: {len(skills)} skills, {coverage:.0f}% JD coverage"
    return build_evidence(
        "resume",
        summary=summary,
        skills=[str(s) for s in skills],
        signals=signals,
        highlights=[str(m) for m in matched[:10]],
        processed={"jd_match": jd_match, "text_length": pkg.get("text_length", 0)},
    )


def normalize_portfolio(pkg: dict[str, Any]) -> EvidenceObject:
    """Portfolio package → evidence."""
    pkg = pkg or {}
    if pkg.get("error"):
        return build_evidence("portfolio", source_url=pkg.get("portfolio_url"), error=str(pkg["error"]))

    skills = pkg.get("skills") or []
    projects = pkg.get("projects") or []
    links = pkg.get("links") or {}

    signals = [
        EvidenceSignal(label="skills_mentioned", detail=f"{len(skills)} skills", value=len(skills)),
        EvidenceSignal(label="projects", detail=f"{len(projects)} projects referenced", value=len(projects)),
    ]
    if links.get("github"):
        signals.append(EvidenceSignal(label="github_link", detail=str(links["github"])))

    summary = f"Portfolio: {len(skills)} skills, {len(projects)} projects, {pkg.get('word_count', 0)} words"
    return build_evidence(
        "portfolio",
        source_url=pkg.get("portfolio_url"),
        summary=summary,
        skills=[str(s) for s in skills],
        signals=signals,
        highlights=[str(p) for p in projects[:10]],
        raw={"title": pkg.get("title"), "links": links},
        processed={"projects": projects, "word_count": pkg.get("word_count", 0)},
    )


_NORMALIZERS = {
    "github": normalize_github,
    "linkedin": normalize_linkedin,
    "leetcode": normalize_leetcode,
    "resume": normalize_resume,
    "portfolio": normalize_portfolio,
}


def normalize(source: str, pkg: dict[str, Any]) -> EvidenceObject:
    """Dispatch to the normalizer for ``source``.

    Unknown sources fall back to a minimal evidence object so callers never
    crash on a new provider type.
    """
    fn = _NORMALIZERS.get(source)
    if fn is None:
        return build_evidence(source, raw=pkg or {})
    return fn(pkg or {})
