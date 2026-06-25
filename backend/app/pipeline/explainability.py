"""Explainability — depth, complexity, cross-project evidence."""

from __future__ import annotations

from app.pipeline.aggregation import CandidateProfile
from app.pipeline.evidence_graph import EvidenceGraph, FeatureEvidenceAggregate
from app.pipeline.skill_assessment import SkillAssessment
from app.pipeline.schemas import EvidenceItem, FeatureEvidence, SkillEvidence


def build_feature_evidence_items(
    repo_name: str,
    features: dict,
    git_metrics: dict,
    maintenance_score: float,
) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for _feat_id, result in features.items():
        detected = result.detected if hasattr(result, "detected") else result.get("detected")
        if not detected:
            continue
        label = result.label if hasattr(result, "label") else result.get("label", _feat_id)
        confidence = result.confidence if hasattr(result, "confidence") else result.get("confidence", 0)
        depth = result.depth if hasattr(result, "depth") else result.get("depth", 0)
        evidence = result.evidence if hasattr(result, "evidence") else result.get("evidence", [])

        items.append(
            EvidenceItem(
                repository=repo_name,
                feature=label,
                signal=f"{label} detected (depth {int(depth * 100)}%)",
                weight=confidence,
                source="github",
                reliability=0.95,
            )
        )
        for ev in evidence[:4]:
            if not ev.startswith("usage:"):
                items.append(
                    EvidenceItem(
                        repository=repo_name,
                        feature=label,
                        signal=ev,
                        weight=confidence,
                        source="github",
                        reliability=0.95,
                    )
                )

    months = git_metrics.get("months_active", 0)
    if months >= 1:
        items.append(
            EvidenceItem(
                repository=repo_name,
                signal=f"maintained {months:.0f} months ({git_metrics.get('total_commits', 0)} commits)",
                weight=maintenance_score / 100,
                source="github",
                reliability=0.95,
            )
        )
    return items


def build_candidate_feature_evidence(
    profile: CandidateProfile,
    graph: EvidenceGraph | None = None,
) -> dict[str, FeatureEvidence]:
    evidence: dict[str, FeatureEvidence] = {}

    if graph:
        for feat_id, agg in graph.feature_aggregates.items():
            evidence[feat_id] = _aggregate_to_schema(agg)
        return evidence

    for feat_id, result in profile.features.items():
        if not result.detected:
            continue
        repos = [r.split("/")[-1] for r in profile.feature_sources.get(feat_id, [])]
        evidence[feat_id] = FeatureEvidence(
            feature=result.label,
            score=result.score,
            depth=result.depth,
            confidence=result.confidence,
            evidence=result.evidence[:8],
            repositories=repos,
            evidence_count=len(result.evidence) * max(len(repos), 1),
            cross_project_strength=0.5 if len(repos) >= 2 else 0.4,
            sub_features=result.sub_features,
            complexity=result.complexity,
            evidence_channels=result.evidence_channels,
            sources=["github"],
        )
    return evidence


def _aggregate_to_schema(agg: FeatureEvidenceAggregate) -> FeatureEvidence:
    all_evidence: list[str] = []
    for source_evs in agg.evidence_by_source.values():
        all_evidence.extend(source_evs)
    es = None
    if agg.evidence_strength:
        from app.pipeline.schemas import EvidenceStrengthSchema
        es = EvidenceStrengthSchema(**agg.evidence_strength.to_dict())
    return FeatureEvidence(
        feature=agg.label,
        score=agg.score,
        depth=agg.depth,
        confidence=agg.confidence,
        evidence=list(dict.fromkeys(all_evidence))[:10],
        repositories=agg.repositories,
        evidence_count=agg.evidence_count,
        cross_project_strength=agg.cross_project_strength,
        evidence_strength=es,
        sub_features=agg.sub_features,
        complexity=agg.complexity,
        sources=agg.sources,
        evidence_by_source=agg.evidence_by_source,
    )


def build_skill_evidence(
    assessments: dict[str, SkillAssessment],
    verified: dict | None = None,
) -> dict[str, SkillEvidence]:
    verified = verified or {}
    out: dict[str, SkillEvidence] = {}
    for skill, a in assessments.items():
        v = verified.get(skill)
        status = v.status if v else a.status
        score = a.score if v and v.verified else (min(a.score, 40) if v and v.status == "weak" else 0)
        if v and v.status in ("claimed", "unknown") and not v.verified:
            status = v.status
            score = 0
        out[skill] = SkillEvidence(
            skill=skill,
            score=score,
            status=status,
            presence=a.presence,
            depth=a.depth / 100,
            confidence=v.confidence if v else a.confidence,
            evidence=(v.github_evidence if v and v.github_evidence else a.evidence),
        )
    return out
