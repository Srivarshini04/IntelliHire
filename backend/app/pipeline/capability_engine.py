"""Capability inference from features via database graph."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.github_intel.models import Capability, EngineeringFeature, FeatureCapabilityEdge
from app.pipeline.aggregation import CandidateProfile
from app.pipeline.evidence_graph import EvidenceGraph


def infer_capabilities_from_profile(
    db: Session,
    profile: CandidateProfile,
    impact_score: float = 0.0,
    graph: EvidenceGraph | None = None,
) -> dict[str, int]:
    cap_totals: dict[str, float] = {c.slug: 0.0 for c in db.query(Capability).all()}
    cap_weights: dict[str, float] = {slug: 0.0 for slug in cap_totals}

    feat_slug_by_id = {f.id: f.slug for f in db.query(EngineeringFeature).all()}
    cap_by_id = {c.id: c.slug for c in db.query(Capability).all()}

    for edge in db.query(FeatureCapabilityEdge).all():
        feat_slug = feat_slug_by_id.get(edge.feature_id)
        cap_slug = cap_by_id.get(edge.capability_id)
        if not feat_slug or not cap_slug:
            continue
        feat = profile.features.get(feat_slug)
        if not feat or not feat.detected:
            continue
        agg = graph.feature_aggregates.get(feat_slug) if graph else None
        if agg and agg.evidence_strength:
            strength_mult = agg.evidence_strength.consistency_index / 100.0
            strength = (feat.confidence * 0.3 + feat.depth * 0.4 + strength_mult * 0.3)
        else:
            strength = feat.confidence * 0.5 + feat.depth * 0.5
        cap_totals[cap_slug] += strength * 100 * edge.weight
        cap_weights[cap_slug] += edge.weight

    caps: dict[str, float] = {}
    for slug, total in cap_totals.items():
        if cap_weights[slug] > 0:
            caps[slug] = min(total / cap_weights[slug], 95)
        else:
            caps[slug] = 0.0

    maintenance_mult = 0.75 + (profile.maintenance_score / 100) * 0.2
    impact_mult = 0.9 + (impact_score / 100) * 0.1
    for slug in caps:
        if caps[slug] > 0:
            caps[slug] = min(caps[slug] * maintenance_mult * impact_mult, 95)

    detected_count = sum(1 for f in profile.features.values() if f.detected and f.depth >= 0.3)
    if detected_count >= 4:
        for slug in ("backend_engineering", "deployment_engineering"):
            if slug in caps and caps[slug] > 0:
                caps[slug] = min(caps[slug] + detected_count, 95)

    return {slug: int(round(score)) for slug, score in caps.items()}
