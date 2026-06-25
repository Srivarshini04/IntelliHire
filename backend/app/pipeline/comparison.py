"""GitHubProfile comparison engine."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.pipeline.orchestrator import run_analysis
from app.pipeline.schemas import AnalyzeResponse, CompareRequest, CompareResponse, ComparisonVerdict


def compare_candidates(db: Session, request: CompareRequest) -> CompareResponse:
    profiles: list[AnalyzeResponse] = []
    for url in request.candidates:
        profiles.append(run_analysis(db, url, request.jd.required_skills))

    if len(profiles) < 2:
        raise ValueError("At least two candidates required for comparison")

    capability_winners: dict[str, str] = {}
    all_caps = set()
    for p in profiles:
        all_caps.update(p.candidate_capabilities.keys())

    for cap in all_caps:
        best = max(profiles, key=lambda p: p.candidate_capabilities.get(cap, 0))
        capability_winners[cap] = best.github_username

    skill_winners: dict[str, str] = {}
    all_skills = set(request.jd.required_skills)
    for p in profiles:
        all_skills.update(p.skill_scores.keys())

    for skill in all_skills:
        best = max(profiles, key=lambda p: p.skill_scores.get(skill, 0))
        skill_winners[skill] = best.github_username

    overall_scores = {
        p.github_username: _overall_score(p) for p in profiles
    }
    winner = max(overall_scores, key=overall_scores.get)  # type: ignore[arg-type]

    verdicts: list[ComparisonVerdict] = []
    for p in profiles:
        username = p.github_username
        strengths = _top_capabilities(p, n=3)
        gaps = _capability_gaps(p, profiles, request.jd.required_skills)
        verdicts.append(
            ComparisonVerdict(
                github_username=username,
                overall_score=overall_scores[username],
                top_capabilities=strengths,
                capability_gaps=gaps,
                detected_features=p.candidate_features,
                maintenance_score=p.metadata.get("maintenance_score", 0),
                summary=_build_summary(p, winner == username, gaps),
            )
        )

    return CompareResponse(
        candidates=profiles,
        winner=winner,
        capability_winners=capability_winners,
        skill_winners=skill_winners,
        verdicts=verdicts,
    )


def _overall_score(profile: AnalyzeResponse) -> int:
    caps = list(profile.candidate_capabilities.values())
    skills = list(profile.skill_scores.values())
    maintenance = profile.metadata.get("maintenance_score", 0)
    cap_avg = sum(caps) / len(caps) if caps else 0
    skill_avg = sum(skills) / len(skills) if skills else 0
    feature_bonus = len(profile.candidate_features) * 3
    return int(min(cap_avg * 0.5 + skill_avg * 0.25 + maintenance * 0.25 + feature_bonus, 95))


def _top_capabilities(profile: AnalyzeResponse, n: int = 3) -> list[str]:
    ranked = sorted(profile.candidate_capabilities.items(), key=lambda x: x[1], reverse=True)
    return [f"{k.replace('_', ' ').title()} ({v})" for k, v in ranked[:n]]


def _capability_gaps(
    profile: AnalyzeResponse,
    all_profiles: list[AnalyzeResponse],
    jd_skills: list[str],
) -> list[str]:
    gaps: list[str] = []
    best_caps = {
        cap: max(p.candidate_capabilities.get(cap, 0) for p in all_profiles)
        for cap in profile.candidate_capabilities
    }
    for cap, best in best_caps.items():
        mine = profile.candidate_capabilities.get(cap, 0)
        if best - mine >= 20:
            gaps.append(f"Lower {cap.replace('_', ' ')} vs peers ({mine} vs {best})")

    for skill in jd_skills:
        if profile.skill_scores.get(skill, 0) < 40:
            gaps.append(f"Weak JD skill: {skill}")

    return gaps[:5]


def _build_summary(profile: AnalyzeResponse, is_winner: bool, gaps: list[str]) -> str:
    features = ", ".join(profile.candidate_features[:5]) or "limited feature evidence"
    maintenance = profile.metadata.get("maintenance_score", 0)
    if is_winner:
        return (
            f"Strongest overall candidate. Demonstrated {features} across "
            f"{profile.metadata.get('repos_analyzed', 0)} repos with "
            f"maintenance score {maintenance:.0f}/100."
        )
    return (
        f"Demonstrated {features} but trails peers on "
        f"{'; '.join(gaps[:2]) or 'overall capability breadth'}."
    )
