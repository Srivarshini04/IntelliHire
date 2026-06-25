"""Cross-repository candidate aggregation — hire people, not repos."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.pipeline.features import FeatureResult


@dataclass
class RepoAnalysisBundle:
    repo_name: str
    features: dict[str, FeatureResult]
    maintenance_score: float
    complexity: dict
    dependencies: set[str]
    git_metrics: dict
    stars: int = 0
    forks: int = 0
    size_kb: int = 0


@dataclass
class CandidateProfile:
    features: dict[str, FeatureResult] = field(default_factory=dict)
    feature_sources: dict[str, list[str]] = field(default_factory=dict)
    feature_months_by_repo: dict[str, dict[str, float]] = field(default_factory=dict)
    feature_maintenance_by_repo: dict[str, dict[str, float]] = field(default_factory=dict)
    maintenance_score: float = 0.0
    maintenance_by_repo: dict[str, float] = field(default_factory=dict)
    total_months_active: float = 0.0
    repos_analyzed: list[str] = field(default_factory=list)
    dependency_union: set[str] = field(default_factory=set)
    engineering_maturity: float = 0.0

    def to_dict(self) -> dict:
        return {
            "features": [f.label for f in self.features.values() if f.detected],
            "feature_details": {k: v.to_dict() for k, v in self.features.items() if v.detected},
            "maintenance_score": round(self.maintenance_score, 1),
            "engineering_maturity": round(self.engineering_maturity, 1),
            "repos_analyzed": self.repos_analyzed,
        }


def _merge_features(existing: FeatureResult, incoming: FeatureResult) -> FeatureResult:
    merged_subs = {**existing.sub_features, **{k: v for k, v in incoming.sub_features.items() if v}}
    active = sum(1 for v in merged_subs.values() if v)
    total = max(len(merged_subs), 1)
    depth = active / total
    evidence = list(dict.fromkeys(existing.evidence + incoming.evidence))[:10]
    channels = {k: existing.evidence_channels.get(k, False) or incoming.evidence_channels.get(k, False)
                for k in set(existing.evidence_channels) | set(incoming.evidence_channels)}
    confidence = min(max(existing.confidence, incoming.confidence) + 0.1, 1.0)
    detected = existing.detected or incoming.detected
    score = int(min(confidence * 60 + depth * 40, 95)) if detected else 0
    return FeatureResult(
        feature_id=existing.feature_id,
        label=existing.label,
        detected=detected,
        confidence=confidence,
        depth=depth,
        score=score,
        sub_features=merged_subs,
        complexity=merged_subs,
        evidence=evidence,
        evidence_channels=channels,
    )


def aggregate_candidate_profile(bundles: list[RepoAnalysisBundle]) -> CandidateProfile:
    profile = CandidateProfile()
    if not bundles:
        return profile

    maintenance_scores: list[float] = []
    months_values: list[float] = []
    feature_depths: list[float] = []

    for bundle in bundles:
        profile.repos_analyzed.append(bundle.repo_name)
        profile.dependency_union |= bundle.dependencies
        maintenance_scores.append(bundle.maintenance_score)
        profile.maintenance_by_repo[bundle.repo_name] = bundle.maintenance_score
        months_values.append(bundle.git_metrics.get("months_active", 0))

        for feat_id, result in bundle.features.items():
            if not result.detected:
                continue
            feature_depths.append(result.depth)
            existing = profile.features.get(feat_id)
            if existing is None:
                profile.features[feat_id] = result
                profile.feature_sources[feat_id] = [bundle.repo_name]
            else:
                profile.features[feat_id] = _merge_features(existing, result)
                profile.feature_sources.setdefault(feat_id, []).append(bundle.repo_name)

            profile.feature_months_by_repo.setdefault(feat_id, {})[bundle.repo_name] = (
                bundle.git_metrics.get("months_active", 0)
            )
            profile.feature_maintenance_by_repo.setdefault(feat_id, {})[bundle.repo_name] = (
                bundle.maintenance_score
            )

    if maintenance_scores:
        best = max(maintenance_scores)
        breadth_bonus = min(len([s for s in maintenance_scores if s >= 40]) * 5, 20)
        profile.maintenance_score = min(
            best * 0.7 + (sum(maintenance_scores) / len(maintenance_scores)) * 0.3 + breadth_bonus, 100
        )

    profile.total_months_active = sum(months_values)
    avg_depth = sum(feature_depths) / len(feature_depths) if feature_depths else 0
    profile.engineering_maturity = min(
        profile.maintenance_score * 0.4 + avg_depth * 100 * 0.35 + len(profile.features) * 5,
        95,
    )
    return profile
