"""Candidate brief-summary engine.

Turns the raw per-source evidence we already store (GitHub, LeetCode, LinkedIn,
Portfolio, Resume) plus the capability/risk/HTI scores into a single, human-
readable brief: what each source said about the candidate, the concrete numbers
behind it, the strengths and weaknesses it implies, and an overall verdict on
how well the person matches the role.

It is fully deterministic (no LLM) so the brief is explainable and reproducible
— every line traces back to a number in the evidence.
"""

from __future__ import annotations

from typing import Any

from app.schemas.candidate import (
    CandidateSummary,
    RoleFitSummary,
    SourceSummary,
    SummaryStat,
)
from app.skills.matching import canonical, is_covered

_SOURCE_TITLES = {
    "github": "GitHub",
    "leetcode": "LeetCode",
    "linkedin": "LinkedIn",
    "portfolio": "Portfolio",
    "resume": "Resume",
}
# Order sources strongest-evidence first.
_SOURCE_ORDER = ["github", "leetcode", "linkedin", "portfolio", "resume"]


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _stat(label: str, value: Any) -> SummaryStat:
    return SummaryStat(label=label, value=str(value))


# --------------------------------------------------------------------------- #
# Per-source builders
# --------------------------------------------------------------------------- #
def _github_summary(pkg: dict) -> SourceSummary:
    repos = pkg.get("repositories_analyzed") or []
    maturity = _num(pkg.get("engineering_maturity"))
    maintenance = _num(pkg.get("maintenance_score"))
    langs = (pkg.get("skills") or {}).get("languages", []) or []
    features = pkg.get("features") or []
    gem = pkg.get("hidden_gem") or {}
    caps = pkg.get("capabilities") or {}

    stats = [
        _stat("Repositories analyzed", len(repos)),
        _stat("Engineering maturity", f"{maturity:.0f}/100"),
        _stat("Maintenance score", f"{maintenance:.2f}"),
    ]
    if langs:
        stats.append(_stat("Top languages", ", ".join(map(str, langs[:5]))))
    if features:
        stats.append(_stat("Production features", len(features)))

    strengths: list[str] = []
    weaknesses: list[str] = []

    if maturity >= 70:
        strengths.append(f"Strong engineering maturity ({maturity:.0f}/100)")
    elif maturity and maturity < 40:
        weaknesses.append(f"Low engineering maturity ({maturity:.0f}/100)")

    if len(repos) >= 3:
        strengths.append(f"Active across {len(repos)} analyzed repositories")
    elif len(repos) <= 1:
        weaknesses.append("Limited public repository activity")

    if features:
        strengths.append("Production-grade features detected: " + ", ".join(map(str, features[:5])))
    else:
        weaknesses.append("No production-grade features detected in code")

    if maintenance and maintenance < 0.3:
        weaknesses.append("Few recent commits — low maintenance signal")

    top_caps = [k.replace("_", " ") for k, v in caps.items() if _num(v) >= 70]
    if top_caps:
        strengths.append("Capability strengths: " + ", ".join(top_caps[:4]))

    if gem.get("hidden_gem") and gem.get("reason"):
        strengths.append(f"Hidden gem: {gem['reason']}")

    headline = f"{len(repos)} repos analyzed · maturity {maturity:.0f}/100"
    if features:
        headline += f" · {len(features)} production features"
    return SourceSummary(
        source="github", title="GitHub", headline=headline,
        stats=stats, strengths=strengths, weaknesses=weaknesses,
    )


def _leetcode_summary(pkg: dict) -> SourceSummary:
    total = int(_num(pkg.get("total_solved")))
    easy = int(_num(pkg.get("easy_solved")))
    med = int(_num(pkg.get("medium_solved")))
    hard = int(_num(pkg.get("hard_solved")))
    coding = _num(pkg.get("coding_skill"))
    tier = pkg.get("tier", "")
    ranking = pkg.get("ranking")
    contest = pkg.get("contest_rating")
    acceptance = pkg.get("acceptance_rate")

    stats = [
        _stat("Total solved", total),
        _stat("Easy / Medium / Hard", f"{easy} / {med} / {hard}"),
        _stat("Coding skill", f"{coding:.0f}/100"),
        _stat("Tier", tier or "—"),
    ]
    if ranking:
        stats.append(_stat("Global rank", f"#{int(_num(ranking)):,}"))
    if contest:
        stats.append(_stat("Contest rating", int(_num(contest))))
    if acceptance is not None:
        stats.append(_stat("Acceptance rate", f"{_num(acceptance):.0f}%"))

    # The engine already produced explainable strengths/improvements.
    strengths = list(pkg.get("strengths") or [])
    if coding:
        strengths.insert(0, f"Coding skill {coding:.0f}/100 ({tier})" if tier else f"Coding skill {coding:.0f}/100")
    weaknesses = list(pkg.get("improvements") or [])

    headline = f"{total} problems solved · {tier} · coding skill {coding:.0f}/100"
    return SourceSummary(
        source="leetcode", title="LeetCode", headline=headline,
        stats=stats, strengths=strengths, weaknesses=weaknesses,
    )


def _linkedin_summary(pkg: dict) -> SourceSummary:
    experiences = pkg.get("experiences") or []
    ownership = str(pkg.get("ownership", "Unknown"))
    production = bool(pkg.get("production"))
    scale = pkg.get("scale") or {}
    skills = (pkg.get("skills") or {}).get("skills", []) or []
    certs = (pkg.get("skills") or {}).get("certifications", []) or []
    features = pkg.get("features") or []

    stats = [
        _stat("Professional roles", len(experiences)),
        _stat("Ownership level", ownership),
        _stat("Production experience", "Yes" if production else "Not stated"),
    ]
    if scale.get("users"):
        stats.append(_stat("Operated at scale", f"~{int(_num(scale.get('users'))):,} users"))
    if certs:
        stats.append(_stat("Certifications", len(certs)))

    strengths: list[str] = []
    weaknesses: list[str] = []

    if production:
        strengths.append("States production / shipped experience")
    else:
        weaknesses.append("No clear production experience stated")

    if ownership.lower() in {"team lead", "individual"}:
        strengths.append(f"Demonstrated ownership ({ownership})")
    elif ownership.lower() in {"", "unknown"}:
        weaknesses.append("Ownership level unclear from profile")

    if len(experiences) >= 3:
        strengths.append(f"{len(experiences)} professional roles on record")
    elif not experiences:
        weaknesses.append("Sparse work history on LinkedIn")

    if features:
        strengths.append("Claimed work: " + ", ".join(map(str, features[:4])))
    if certs:
        strengths.append("Certifications: " + ", ".join(map(str, certs[:3])))

    headline = f"{len(experiences)} roles · ownership: {ownership}"
    return SourceSummary(
        source="linkedin", title="LinkedIn", headline=headline,
        stats=stats, strengths=strengths, weaknesses=weaknesses,
    )


def _portfolio_summary(pkg: dict) -> SourceSummary:
    projects = pkg.get("projects") or []
    skills = pkg.get("skills") or []
    words = int(_num(pkg.get("word_count")))
    links = pkg.get("links") or {}
    matched = (pkg.get("jd_match") or {}).get("matched") or []

    stats = [
        _stat("Projects referenced", len(projects)),
        _stat("Skills mentioned", len(skills)),
        _stat("Content length", f"{words} words"),
    ]
    if links:
        stats.append(_stat("Outbound links", ", ".join(links.keys())))

    strengths: list[str] = []
    weaknesses: list[str] = []
    if projects:
        strengths.append("Showcases projects: " + ", ".join(map(str, projects[:4])))
    if matched:
        strengths.append("Role-relevant skills shown: " + ", ".join(map(str, matched[:5])))
    if words < 150:
        weaknesses.append("Thin portfolio content")
    if not links:
        weaknesses.append("No outbound project/code links")

    headline = f"{len(projects)} projects · {len(skills)} skills"
    return SourceSummary(
        source="portfolio", title="Portfolio", headline=headline,
        stats=stats, strengths=strengths, weaknesses=weaknesses,
    )


def _resume_summary(pkg: dict) -> SourceSummary:
    skills = pkg.get("skills") or []
    jd = pkg.get("jd_match") or {}
    required = jd.get("required") or []
    matched = jd.get("matched") or []
    coverage = _num(jd.get("coverage"))
    missing = [r for r in required if r not in matched]

    stats = [
        _stat("Skills extracted", len(skills)),
        _stat("JD skill coverage", f"{coverage:.0f}%"),
    ]
    if matched:
        stats.append(_stat("Matched skills", ", ".join(map(str, matched[:6]))))

    strengths: list[str] = []
    weaknesses: list[str] = []
    if matched:
        strengths.append(f"Covers {len(matched)}/{len(required)} required skills" if required else f"{len(skills)} skills listed")
    if coverage and coverage < 50 and required:
        weaknesses.append(f"Resume covers only {coverage:.0f}% of required skills")
    if missing:
        weaknesses.append("Missing from resume: " + ", ".join(map(str, missing[:6])))

    headline = f"{len(skills)} skills · {coverage:.0f}% JD coverage"
    return SourceSummary(
        source="resume", title="Resume", headline=headline,
        stats=stats, strengths=strengths, weaknesses=weaknesses,
    )


_BUILDERS = {
    "github": _github_summary,
    "leetcode": _leetcode_summary,
    "linkedin": _linkedin_summary,
    "portfolio": _portfolio_summary,
    "resume": _resume_summary,
}


# --------------------------------------------------------------------------- #
# Role fit
# --------------------------------------------------------------------------- #
def _matched_skills(evidence_by_source: dict[str, dict], required: list[str]) -> list[str]:
    """A required skill counts as matched if any source evidences it."""
    if not required:
        return []
    # Collect candidate skill lists + free-text per source.
    skill_lists: list[list[str]] = []
    texts: list[str] = []
    for source, pkg in evidence_by_source.items():
        if source == "github":
            skill_lists.append((pkg.get("skills") or {}).get("languages", []) or [])
        elif source == "linkedin":
            skill_lists.append((pkg.get("skills") or {}).get("skills", []) or [])
        elif source in {"resume", "portfolio"}:
            skill_lists.append(pkg.get("skills") or [])
            texts.append(" ".join(map(str, (pkg.get("jd_match") or {}).get("matched") or [])))

    all_skills: list[str] = [s for lst in skill_lists for s in lst]
    text_blob = " ".join(texts)
    matched: list[str] = []
    for req in required:
        if is_covered(req, skills=all_skills, text=text_blob):
            matched.append(req)
    # de-dup preserving order
    seen: set[str] = set()
    out: list[str] = []
    for m in matched:
        key = canonical(m)
        if key not in seen:
            seen.add(key)
            out.append(m)
    return out


def _role_fit(
    evidence_by_source: dict[str, dict],
    required: list[str],
    risk: dict | None,
) -> RoleFitSummary:
    matched = _matched_skills(evidence_by_source, required)
    missing = [r for r in required if canonical(r) not in {canonical(m) for m in matched}]

    role_gap = _num((risk or {}).get("role_gap_risk")) if risk else 0.0
    if risk and risk.get("role_gap_risk") is not None:
        fit_score = round(max(0.0, 100.0 - role_gap), 1)
    elif required:
        fit_score = round(len(matched) / len(required) * 100.0, 1)
    else:
        fit_score = 50.0

    if fit_score >= 65:
        verdict = "Strong match"
    elif fit_score >= 40:
        verdict = "Partial match"
    else:
        verdict = "Weak match"

    if required:
        reason = (
            f"Evidences {len(matched)} of {len(required)} required skills "
            f"({', '.join(matched[:5]) or 'none'})."
        )
        if missing:
            reason += f" Gaps: {', '.join(missing[:5])}."
    else:
        reason = "No required skills defined for this role."

    return RoleFitSummary(
        verdict=verdict,
        fit_score=fit_score,
        matched_skills=matched,
        missing_skills=missing,
        reason=reason,
    )


_HAS_DATA = {
    "github": lambda p: bool(p.get("repositories_analyzed") or p.get("features") or (p.get("skills") or {}).get("languages")),
    "leetcode": lambda p: bool(_num(p.get("total_solved")) or _num(p.get("coding_skill"))),
    "linkedin": lambda p: bool(
        p.get("available", p.get("experiences") or (p.get("skills") or {}).get("skills") or p.get("features"))
    ),
    "portfolio": lambda p: bool(p.get("projects") or p.get("skills")),
    "resume": lambda p: bool(p.get("skills") or (p.get("profile") or {})),
}


def _unavailable_note(source: str, pkg: dict) -> str | None:
    """Return a reason string when a source produced no usable data, else None."""
    if pkg.get("error"):
        return str(pkg["error"])
    has_data = _HAS_DATA.get(source)
    if has_data and not has_data(pkg):
        return "No data could be retrieved from this source."
    return None


def _unavailable_summary(source: str, title: str, note: str) -> SourceSummary:
    """A neutral card for a source we couldn't read — never counts as a weakness."""
    return SourceSummary(
        source=source,
        title=title,
        headline=note,
        available=False,
        stats=[SummaryStat(label="Status", value="Not available")],
        strengths=[],
        weaknesses=[],
    )


# --------------------------------------------------------------------------- #
# Top-level
# --------------------------------------------------------------------------- #
def _overall(sources: list[SourceSummary], capability: dict | None, risk: dict | None) -> tuple[list[str], list[str]]:
    strengths: list[str] = []
    weaknesses: list[str] = []
    # Take the leading strength/weakness from each source (already ranked).
    for src in sources:
        if src.strengths:
            strengths.append(f"[{src.title}] {src.strengths[0]}")
        if src.weaknesses:
            weaknesses.append(f"[{src.title}] {src.weaknesses[0]}")

    if risk:
        if _num(risk.get("credibility_risk")) >= 70:
            weaknesses.append("Credibility risk high — claims not corroborated by verifiable evidence")
        if _num(risk.get("evidence_risk")) >= 70:
            weaknesses.append("Limited verifiable evidence across sources")
    if capability and _num(capability.get("capability_score")) >= 70:
        strengths.append(f"Strong overall capability ({_num(capability.get('capability_score')):.0f}/100)")

    return strengths[:8], weaknesses[:8]


def build_candidate_summary(
    name: str,
    evidence_by_source: dict[str, dict],
    capability: dict | None = None,
    risk: dict | None = None,
    hti: dict | None = None,
    required_skills: list[str] | None = None,
) -> CandidateSummary:
    """Assemble the holistic brief from per-source evidence + scores."""
    required = [str(s) for s in (required_skills or []) if str(s).strip()]

    sources: list[SourceSummary] = []
    for source in _SOURCE_ORDER:
        pkg = evidence_by_source.get(source)
        if not pkg:
            continue
        note = _unavailable_note(source, pkg)
        if note:
            # Show the source, but as "not available" — don't fabricate weaknesses
            # for data we never received (e.g. LinkedIn when Apify isn't configured).
            sources.append(_unavailable_summary(source, _SOURCE_TITLES.get(source, source.title()), note))
            continue
        builder = _BUILDERS.get(source)
        if builder:
            sources.append(builder(pkg))

    role_fit = _role_fit(evidence_by_source, required, risk)
    overall_strengths, overall_weaknesses = _overall(sources, capability, risk)

    cap_score = _num((capability or {}).get("capability_score"))
    hti_score = _num((hti or {}).get("hti_score"))
    analyzed = [s.title for s in sources if s.available]
    source_names = ", ".join(analyzed) or "resume"
    headline = (
        f"{name} — {role_fit.verdict.lower()} for this role. "
        f"Capability {cap_score:.0f}/100, HTI {hti_score:.0f}. "
        f"Analyzed from: {source_names}."
    )

    return CandidateSummary(
        headline=headline,
        role_fit=role_fit,
        sources=sources,
        overall_strengths=overall_strengths,
        overall_weaknesses=overall_weaknesses,
    )
