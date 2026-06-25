"""Weighted evidence graph — cross-source, cross-project."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.pipeline.aggregation import CandidateProfile
from app.pipeline.evidence_sources import SOURCE_RELIABILITY, reliability
from app.pipeline.evidence_strength import EvidenceStrength, adjust_score_with_strength, compute_evidence_strength
from app.pipeline.features import FEATURE_HIERARCHY


@dataclass
class EvidenceNode:
    source: str
    reliability: float
    signal: str
    feature_id: str | None = None
    skill: str | None = None
    repository: str | None = None
    organization: str | None = None
    is_claim: bool = False

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "reliability": self.reliability,
            "signal": self.signal,
            "feature_id": self.feature_id,
            "skill": self.skill,
            "repository": self.repository,
            "organization": self.organization,
            "is_claim": self.is_claim,
        }


@dataclass
class FeatureEvidenceAggregate:
    feature_id: str
    label: str
    score: int
    depth: float
    confidence: float
    repositories: list[str]
    evidence_count: int
    cross_project_strength: float
    sources: list[str]
    evidence_by_source: dict[str, list[str]]
    sub_features: dict[str, bool] = field(default_factory=dict)
    complexity: dict[str, bool] = field(default_factory=dict)
    evidence_strength: EvidenceStrength | None = None

    def detected_summary(self) -> str:
        if self.repositories:
            months = self.evidence_strength.months_observed if self.evidence_strength else 0
            return (
                f"{self.label} demonstrated in {', '.join(self.repositories[:2])} "
                f"({self.evidence_count} signals, {months:.0f} months observed)"
            )
        return f"{self.label} claimed via {', '.join(self.sources)} ({self.evidence_count} signals)"

    def to_dict(self) -> dict:
        return {
            "feature_id": self.feature_id,
            "feature": self.label,
            "score": self.score,
            "depth": round(self.depth, 2),
            "confidence": round(self.confidence, 2),
            "repositories": self.repositories,
            "evidence_count": self.evidence_count,
            "cross_project_strength": round(self.cross_project_strength, 2),
            "sources": self.sources,
            "evidence_by_source": self.evidence_by_source,
            "sub_features": self.sub_features,
            "complexity": self.complexity,
            "evidence_strength": self.evidence_strength.to_dict() if self.evidence_strength else None,
        }


def compute_cross_project_strength(
    repo_count: int,
    total_repos_analyzed: int,
    depth: float,
) -> float:
    """Repeated demonstration across independent projects = stronger signal."""
    if repo_count <= 0:
        return 0.0
    if repo_count == 1:
        return round(min(0.45 + depth * 0.25, 0.65), 2)
    breadth = min(repo_count / max(total_repos_analyzed, 1), 1.0)
    return round(min(0.55 + breadth * 0.30 + depth * 0.15, 0.95), 2)


@dataclass
class EvidenceGraph:
    nodes: list[EvidenceNode] = field(default_factory=list)
    feature_aggregates: dict[str, FeatureEvidenceAggregate] = field(default_factory=dict)

    def add_node(self, node: EvidenceNode) -> None:
        self.nodes.append(node)

    def add_github_feature(
        self,
        feature_id: str,
        label: str,
        repository: str,
        evidence: list[str],
        depth: float,
        score: int,
        confidence: float,
        sub_features: dict[str, bool],
    ) -> None:
        rel = reliability("github")
        for ev in evidence:
            self.add_node(EvidenceNode(
                source="github",
                reliability=rel,
                signal=ev,
                feature_id=feature_id,
                repository=repository,
                is_claim=False,
            ))

    def add_claim(
        self,
        source: str,
        signal: str,
        *,
        feature_id: str | None = None,
        skill: str | None = None,
        organization: str | None = None,
    ) -> None:
        self.add_node(EvidenceNode(
            source=source,
            reliability=reliability(source),
            signal=signal,
            feature_id=feature_id,
            skill=skill,
            organization=organization,
            is_claim=True,
        ))

    def build_from_github_profile(self, profile: CandidateProfile) -> None:
        total_repos = len(profile.repos_analyzed)
        for feat_id, feat in profile.features.items():
            if not feat.detected:
                continue
            repos = list(dict.fromkeys(profile.feature_sources.get(feat_id, [])))
            repo_short = [r.split("/")[-1] if "/" in r else r for r in repos]
            evidence_count = len(feat.evidence) * len(repos)

            months_map = profile.feature_months_by_repo.get(feat_id, {})
            maint_map = profile.feature_maintenance_by_repo.get(feat_id, {})
            months_observed = sum(months_map.get(r, 0) for r in repos)
            avg_maint = sum(maint_map.get(r, 0) for r in repos) / max(len(repos), 1)

            for repo in repos:
                self.add_github_feature(
                    feat_id, feat.label, repo, feat.evidence,
                    feat.depth, feat.score, feat.confidence, feat.sub_features,
                )

            cross = compute_cross_project_strength(len(repos), total_repos, feat.depth)
            strength = compute_evidence_strength(
                repository_count=len(repos),
                months_observed=months_observed,
                maintenance_score=avg_maint,
                cross_project_strength=cross,
                depth=feat.depth,
            )
            base_score = feat.score
            adjusted_score = adjust_score_with_strength(base_score, strength)

            weighted_conf = min(
                feat.confidence * reliability("github") * 0.5
                + cross * 0.25
                + (strength.consistency_index / 100) * 0.25,
                0.98,
            )

            self.feature_aggregates[feat_id] = FeatureEvidenceAggregate(
                feature_id=feat_id,
                label=feat.label,
                score=adjusted_score,
                depth=feat.depth,
                confidence=weighted_conf,
                repositories=repo_short,
                evidence_count=evidence_count,
                cross_project_strength=cross,
                sources=["github"],
                evidence_by_source={"github": feat.evidence[:8]},
                sub_features=feat.sub_features,
                complexity=feat.complexity,
                evidence_strength=strength,
            )

    def merge_linkedin_features(
        self,
        linkedin_features: dict[str, list[str]],
        linkedin_evidence: dict[str, list[str]],
    ) -> None:
        """Merge LinkedIn claims into graph with lower reliability."""
        label_to_id = {spec["label"].lower(): fid for fid, spec in FEATURE_HIERARCHY.items()}
        label_to_id.update({fid.replace("_", " ").lower(): fid for fid in FEATURE_HIERARCHY})

        for feature_label, orgs in linkedin_features.items():
            feat_id = label_to_id.get(feature_label.lower())
            if not feat_id:
                continue
            ev_list = linkedin_evidence.get(feature_label, [])
            for ev in ev_list:
                self.add_claim("linkedin", ev, feature_id=feat_id, organization=orgs[0] if orgs else None)

            agg = self.feature_aggregates.get(feat_id)
            li_conf = reliability("linkedin") * 0.5
            if agg:
                agg.sources = list(dict.fromkeys(agg.sources + ["linkedin"]))
                agg.evidence_by_source.setdefault("linkedin", []).extend(ev_list[:5])
                agg.evidence_count += len(ev_list)
                agg.confidence = min(agg.confidence * 0.7 + li_conf * 0.3 + 0.05, 0.98)
            else:
                self.feature_aggregates[feat_id] = FeatureEvidenceAggregate(
                    feature_id=feat_id,
                    label=FEATURE_HIERARCHY[feat_id]["label"],
                    score=0,
                    depth=0.0,
                    confidence=li_conf,
                    repositories=[],
                    evidence_count=len(ev_list),
                    cross_project_strength=0.0,
                    sources=["linkedin"],
                    evidence_by_source={"linkedin": ev_list[:5]},
                )

    def weighted_feature_confidence(self, feature_id: str) -> float:
        nodes = [n for n in self.nodes if n.feature_id == feature_id and not n.is_claim]
        if not nodes:
            nodes = [n for n in self.nodes if n.feature_id == feature_id]
        if not nodes:
            return 0.0
        total_weight = sum(n.reliability for n in nodes)
        return sum(n.reliability for n in nodes) / total_weight if total_weight else 0.0

    def to_dict(self) -> dict:
        return {
            "node_count": len(self.nodes),
            "sources_present": list(dict.fromkeys(n.source for n in self.nodes)),
            "source_reliability": SOURCE_RELIABILITY,
            "features": {k: v.to_dict() for k, v in self.feature_aggregates.items()},
            "nodes": [n.to_dict() for n in self.nodes[:50]],
        }

    def recruiter_lines(self) -> list[str]:
        lines: list[str] = []
        for agg in self.feature_aggregates.values():
            es = agg.evidence_strength
            if es and es.repository_count >= 2 and es.months_observed >= 6:
                lines.append(
                    f"{agg.label} observed across {es.independent_projects} independent projects "
                    f"over {es.months_observed:.0f} months — consistency {es.consistency_index:.0f}/100"
                )
            elif agg.cross_project_strength >= 0.55 and len(agg.repositories) >= 2:
                lines.append(
                    f"{agg.label} observed across {len(agg.repositories)} independent projects "
                    f"({', '.join(agg.repositories[:3])}) — cross-project strength {agg.cross_project_strength:.0%}"
                )
            elif agg.detected_summary():
                lines.append(agg.detected_summary())
        return lines[:8]
