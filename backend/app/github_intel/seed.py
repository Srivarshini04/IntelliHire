"""Seed capability graph for GitHub intelligence pipeline."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.github_intel.models import (
    Capability,
    EngineeringFeature,
    FeatureCapabilityEdge,
    Skill,
    SkillCapabilityEdge,
)

CAPABILITIES = [
    ("backend_engineering", "Backend Engineering"),
    ("database_engineering", "Database Engineering"),
    ("deployment_engineering", "Deployment Engineering"),
    ("frontend_engineering", "Frontend Engineering"),
    ("data_engineering", "Data Engineering"),
    ("ml_engineering", "ML Engineering"),
]

SKILLS = [
    ("FastAPI", ["fast api", "python api"]),
    ("PostgreSQL", ["postgres", "psql"]),
    ("AWS", ["amazon web services", "cloud"]),
    ("Redis", ["caching"]),
    ("Docker", ["containerization"]),
    ("React", ["frontend", "reactjs"]),
    ("Node.js", ["nodejs", "express"]),
    ("pytest", ["unit testing"]),
    ("Kubernetes", ["k8s"]),
    ("Airflow", ["workflow orchestration"]),
]

SKILL_CAPABILITY = {
    "FastAPI": [("backend_engineering", 1.0)],
    "PostgreSQL": [("database_engineering", 1.0), ("backend_engineering", 0.5)],
    "AWS": [("deployment_engineering", 1.0), ("backend_engineering", 0.4)],
    "Redis": [("backend_engineering", 0.7), ("database_engineering", 0.3)],
    "Docker": [("deployment_engineering", 1.0)],
    "React": [("frontend_engineering", 1.0)],
    "Node.js": [("backend_engineering", 0.8)],
    "pytest": [("backend_engineering", 0.5), ("deployment_engineering", 0.3)],
    "Kubernetes": [("deployment_engineering", 1.0)],
    "Airflow": [("data_engineering", 1.0)],
}

FEATURE_CAPABILITY = {
    "authentication": [("backend_engineering", 0.9)],
    "role_based_access_control": [("backend_engineering", 1.0)],
    "scheduling": [("backend_engineering", 0.8), ("data_engineering", 0.5)],
    "caching": [("backend_engineering", 0.7), ("database_engineering", 0.4)],
    "notifications": [("backend_engineering", 0.6)],
    "payments": [("backend_engineering", 1.0)],
    "messaging": [("backend_engineering", 0.8), ("deployment_engineering", 0.4)],
    "audit_trail": [("backend_engineering", 0.7)],
    "api_design": [("backend_engineering", 1.0)],
    "database_design": [("database_engineering", 1.0), ("backend_engineering", 0.5)],
    "testing": [("backend_engineering", 0.6), ("deployment_engineering", 0.5), ("frontend_engineering", 0.4)],
    "ci_cd": [("deployment_engineering", 1.0)],
    "containerization": [("deployment_engineering", 0.9)],
    "monitoring": [("deployment_engineering", 0.8), ("backend_engineering", 0.5)],
    "distributed_systems": [("backend_engineering", 1.0), ("deployment_engineering", 0.6)],
    "cloud_aws": [("deployment_engineering", 1.0), ("backend_engineering", 0.5)],
}


def seed_capability_graph(db: Session) -> None:
    if db.query(Capability).count() > 0:
        return

    cap_map: dict[str, Capability] = {}
    for slug, label in CAPABILITIES:
        cap = Capability(slug=slug, label=label)
        db.add(cap)
        cap_map[slug] = cap
    db.flush()

    skill_map: dict[str, Skill] = {}
    for name, aliases in SKILLS:
        skill = Skill(name=name, aliases_json=str(aliases).replace("'", '"'))
        db.add(skill)
        skill_map[name] = skill
    db.flush()

    feat_map: dict[str, EngineeringFeature] = {}
    for slug in FEATURE_CAPABILITY:
        label = slug.replace("_", " ").title()
        feat = EngineeringFeature(slug=slug, label=label)
        db.add(feat)
        feat_map[slug] = feat
    db.flush()

    for skill_name, edges in SKILL_CAPABILITY.items():
        skill = skill_map[skill_name]
        for cap_slug, weight in edges:
            db.add(
                SkillCapabilityEdge(
                    skill_id=skill.id, capability_id=cap_map[cap_slug].id, weight=weight
                )
            )

    for feat_slug, edges in FEATURE_CAPABILITY.items():
        feat = feat_map[feat_slug]
        for cap_slug, weight in edges:
            db.add(
                FeatureCapabilityEdge(
                    feature_id=feat.id, capability_id=cap_map[cap_slug].id, weight=weight
                )
            )

    db.commit()
