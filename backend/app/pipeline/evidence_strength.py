"""Evidence strength — consistency over time and across projects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvidenceStrength:
    repository_count: int = 0
    independent_projects: int = 0
    months_observed: float = 0.0
    maintenance_score: float = 0.0
    consistency_index: float = 0.0  # 0-100 composite strength

    def to_dict(self) -> dict:
        return {
            "repository_count": self.repository_count,
            "independent_projects": self.independent_projects,
            "months_observed": round(self.months_observed, 1),
            "maintenance_score": round(self.maintenance_score, 1),
            "consistency_index": round(self.consistency_index, 1),
        }


def compute_evidence_strength(
    repository_count: int,
    months_observed: float,
    maintenance_score: float,
    cross_project_strength: float,
    depth: float,
) -> EvidenceStrength:
    """
  GitHubProfile A: 1 repo, 2 months → low consistency
  GitHubProfile B: 5 repos, 36 months → high consistency
    Same sub-features, very different strength.
    """
    repo_factor = min(repository_count / 5.0, 1.0)
    months_factor = min(months_observed / 36.0, 1.0)
    maint_factor = maintenance_score / 100.0

    consistency = (
        repo_factor * 35.0
        + months_factor * 35.0
        + cross_project_strength * 100.0 * 0.15
        + maint_factor * 10.0
        + depth * 5.0
    )
    consistency = min(consistency, 100.0)

    return EvidenceStrength(
        repository_count=repository_count,
        independent_projects=repository_count,
        months_observed=months_observed,
        maintenance_score=maintenance_score,
        consistency_index=consistency,
    )


def adjust_score_with_strength(base_score: int, strength: EvidenceStrength) -> int:
    """1-repo weekend project cannot score like 5-repo multi-year pattern."""
    if strength.repository_count <= 1 and strength.months_observed < 6:
        cap = min(55 + int(strength.consistency_index * 0.15), 68)
        return min(base_score, cap)
    multiplier = 0.55 + (strength.consistency_index / 100.0) * 0.45
    return int(min(base_score * multiplier + strength.consistency_index * 0.15, 95))
