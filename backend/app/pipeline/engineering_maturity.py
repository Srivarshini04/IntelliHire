"""Step 7 — Engineering maturity dimensions from demonstrated features."""

from __future__ import annotations

from app.pipeline.aggregation import CandidateProfile


def _feature_score(profile: CandidateProfile, *feature_ids: str) -> int:
    depths: list[float] = []
    for fid in feature_ids:
        feat = profile.features.get(fid)
        if feat and feat.detected:
            depths.append(feat.depth)
    if not depths:
        return 0
    return int(min(sum(depths) / len(depths) * 100, 95))


def compute_maturity_breakdown(profile: CandidateProfile) -> dict[str, int]:
    architecture = _feature_score(profile, "api_design", "database_design", "distributed_systems")
    testing = _feature_score(profile, "testing")
    security = _feature_score(profile, "authentication", "role_based_access_control")
    deployment = _feature_score(profile, "ci_cd", "containerization", "cloud_aws")
    maintenance = int(min(profile.maintenance_score, 95))
    observability = _feature_score(profile, "monitoring")

    dimensions = {
        "architecture": architecture,
        "testing": testing,
        "security": security,
        "deployment": deployment,
        "maintenance": maintenance,
        "observability": observability,
    }
    nonzero = [v for v in dimensions.values() if v > 0]
    overall = int(min(sum(nonzero) / len(nonzero), 95)) if nonzero else 0
    dimensions["overall"] = overall
    return dimensions
