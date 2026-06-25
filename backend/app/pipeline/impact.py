"""Project impact signals — stars, forks, community usage."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RepoImpact:
    repo_name: str
    stars: int = 0
    forks: int = 0
    size_kb: int = 0
    impact_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "repo": self.repo_name,
            "stars": self.stars,
            "forks": self.forks,
            "size_kb": self.size_kb,
            "impact_score": round(self.impact_score, 1),
        }


@dataclass
class CandidateImpact:
    total_stars: int = 0
    total_forks: int = 0
    max_repo_stars: int = 0
    repos_with_traction: int = 0
    impact_score: float = 0.0
    repo_impacts: list[RepoImpact] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_stars": self.total_stars,
            "total_forks": self.total_forks,
            "max_repo_stars": self.max_repo_stars,
            "repos_with_traction": self.repos_with_traction,
            "impact_score": round(self.impact_score, 1),
            "repos": [r.to_dict() for r in self.repo_impacts],
        }


def compute_repo_impact(repo_name: str, stars: int, forks: int, size_kb: int) -> RepoImpact:
    star_score = min(stars / 100, 1.0) * 50
    fork_score = min(forks / 20, 1.0) * 30
    size_score = min(size_kb / 3000, 1.0) * 20
    return RepoImpact(
        repo_name=repo_name,
        stars=stars,
        forks=forks,
        size_kb=size_kb,
        impact_score=min(star_score + fork_score + size_score, 100),
    )


def aggregate_impact(repo_data: list[tuple[str, int, int, int]]) -> CandidateImpact:
    impact = CandidateImpact()
    for name, stars, forks, size_kb in repo_data:
        ri = compute_repo_impact(name, stars, forks, size_kb)
        impact.repo_impacts.append(ri)
        impact.total_stars += stars
        impact.total_forks += forks
        impact.max_repo_stars = max(impact.max_repo_stars, stars)
        if stars >= 10 or forks >= 3:
            impact.repos_with_traction += 1

    if impact.repo_impacts:
        impact.impact_score = min(
            sum(r.impact_score for r in impact.repo_impacts) / len(impact.repo_impacts)
            + impact.repos_with_traction * 5,
            100,
        )
    return impact
