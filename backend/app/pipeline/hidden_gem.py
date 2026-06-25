"""Hidden gem detection — strong engineering, weak traditional signals."""

from __future__ import annotations

from dataclasses import dataclass

from app.pipeline.aggregation import CandidateProfile
from app.pipeline.impact import CandidateImpact

PRODUCTION_FEATURES = {
    "authentication", "role_based_access_control", "caching", "testing",
    "ci_cd", "containerization", "database_design", "monitoring",
}


@dataclass
class HiddenGemResult:
    hidden_gem: bool
    reason: str
    production_feature_count: int
    engineering_maturity: float

    def to_dict(self) -> dict:
        return {
            "hidden_gem": self.hidden_gem,
            "reason": self.reason,
            "production_feature_count": self.production_feature_count,
            "engineering_maturity": round(self.engineering_maturity, 1),
        }


def detect_hidden_gem(
    profile: CandidateProfile,
    impact: CandidateImpact,
    capabilities: dict[str, int],
    maturity: dict[str, int] | None = None,
) -> HiddenGemResult:
    prod_features = [
        fid for fid in PRODUCTION_FEATURES
        if profile.features.get(fid) and profile.features[fid].detected
    ]
    prod_count = len(prod_features)
    backend = capabilities.get("backend_engineering", 0)
    deployment = capabilities.get("deployment_engineering", 0)
    mat_overall = (maturity or {}).get("overall", 0)
    maturity_score = mat_overall or (backend + deployment + profile.maintenance_score) / 3

    low_traditional = impact.max_repo_stars < 50 and impact.total_stars < 200
    deep_features = sum(
        1 for f in profile.features.values() if f.detected and f.depth >= 0.5
    )
    strong_engineering = prod_count >= 4 and (backend >= 55 or mat_overall >= 55)
    strong_depth = deep_features >= 3 and profile.maintenance_score >= 40

    if (strong_engineering or strong_depth) and low_traditional:
        return HiddenGemResult(
            hidden_gem=True,
            reason=(
                f"Demonstrated {prod_count} production features with depth across "
                f"{len(profile.repos_analyzed)} repos (maturity {maturity_score:.0f}/100) "
                "despite limited public traction — engineering evidence exceeds traditional credentials."
            ),
            production_feature_count=prod_count,
            engineering_maturity=maturity_score,
        )

    return HiddenGemResult(
        hidden_gem=False,
        reason="Engineering signals align with public project traction and credential signals.",
        production_feature_count=prod_count,
        engineering_maturity=maturity_score,
    )
