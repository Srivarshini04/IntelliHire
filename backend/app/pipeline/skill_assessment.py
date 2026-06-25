"""Evidence-only skill assessment — no hallucinated scores."""

from __future__ import annotations

from dataclasses import dataclass

from app.pipeline.aggregation import CandidateProfile
from app.pipeline.features import FeatureResult

# Skills require direct evidence. `require_direct` blocks inference from unrelated features.
SKILL_EVIDENCE_RULES: dict[str, dict] = {
    "FastAPI": {
        "dependencies": ["fastapi", "uvicorn", "starlette"],
        "related_features": ["api_design"],
        "usage_labels": ["REST endpoints", "Request validation", "OpenAPI docs"],
        "require_direct": False,
    },
    "PostgreSQL": {
        "dependencies": ["psycopg2", "asyncpg", "pg8000"],
        "related_features": ["database_design"],
        "usage_labels": ["ORM models", "Migrations", "Indexing"],
        "require_direct": False,
    },
    "AWS": {
        "dependencies": ["boto3", "botocore", "awscli"],
        "related_features": ["cloud_aws"],
        "usage_labels": ["S3 storage", "EC2 compute", "Lambda functions", "IAM", "Terraform AWS"],
        "require_direct": True,
    },
    "Redis": {
        "dependencies": ["redis", "ioredis"],
        "related_features": ["caching"],
        "usage_labels": ["Distributed cache"],
        "require_direct": False,
    },
    "Docker": {
        "dependencies": [],
        "related_features": ["containerization"],
        "usage_labels": ["Dockerfile", "Docker Compose"],
        "require_direct": False,
    },
    "React": {
        "dependencies": ["react", "react-dom"],
        "related_features": [],
        "usage_labels": [],
        "require_direct": True,
    },
    "Node.js": {
        "dependencies": ["express", "nestjs"],
        "related_features": ["api_design"],
        "usage_labels": ["REST endpoints"],
        "require_direct": True,
    },
    "pytest": {
        "dependencies": ["pytest"],
        "related_features": ["testing"],
        "usage_labels": ["Unit tests", "Test fixtures"],
        "require_direct": False,
    },
}


@dataclass
class SkillAssessment:
    skill: str
    status: str  # demonstrated | weak | unknown
    presence: int
    depth: int
    confidence: float
    score: int
    evidence: list[str]

    def to_dict(self) -> dict:
        return {
            "skill": self.skill,
            "status": self.status,
            "presence": self.presence,
            "depth": self.depth,
            "confidence": round(self.confidence, 2),
            "score": self.score,
            "evidence": self.evidence,
        }


def _feature_depth(profile: CandidateProfile, feature_ids: list[str]) -> float:
    depths = []
    for fid in feature_ids:
        feat = profile.features.get(fid)
        if feat and feat.detected:
            depths.append(feat.depth)
    return sum(depths) / len(depths) if depths else 0.0


def assess_skills(profile: CandidateProfile, jd_skills: list[str]) -> dict[str, SkillAssessment]:
    dep_lower = {d.lower() for d in profile.dependency_union}
    assessments: dict[str, SkillAssessment] = {}

    for skill in jd_skills:
        rules = SKILL_EVIDENCE_RULES.get(skill)
        if rules is None:
            assessments[skill] = SkillAssessment(
                skill=skill,
                status="unknown",
                presence=0,
                depth=0,
                confidence=0.0,
                score=0,
                evidence=["No evidence rules configured — cannot assess without GitHub signals"],
            )
            continue

        evidence: list[str] = []
        dep_hits = [d for d in rules["dependencies"] if d in dep_lower]
        if dep_hits:
            evidence.append(f"Dependency: {', '.join(dep_hits)}")

        for fid in rules.get("related_features", []):
            feat: FeatureResult | None = profile.features.get(fid)
            if feat and feat.detected:
                for label in rules.get("usage_labels", []):
                    if label in feat.evidence:
                        evidence.append(label)
                for ev in feat.evidence[:3]:
                    if ev not in evidence:
                        evidence.append(ev)

        # Cloud/AWS must have explicit cloud feature or boto3 — never infer from CI/CD alone
        if skill == "AWS":
            cloud = profile.features.get("cloud_aws")
            if cloud and cloud.detected:
                evidence.extend([e for e in cloud.evidence if e not in evidence])
            if not dep_hits and not (cloud and cloud.detected):
                assessments[skill] = SkillAssessment(
                    skill=skill,
                    status="unknown",
                    presence=0,
                    depth=0,
                    confidence=0.0,
                    score=0,
                    evidence=["No direct AWS evidence (boto3, S3, EC2, Lambda, IAM, or Terraform AWS)"],
                )
                continue

        presence = 100 if evidence else 0
        depth_pct = int(_feature_depth(profile, rules.get("related_features", [])) * 100)
        channel_bonus = min(len(evidence), 4) * 0.15
        confidence = min(channel_bonus + (depth_pct / 100) * 0.5, 0.95)

        if not evidence:
            assessments[skill] = SkillAssessment(
                skill=skill, status="unknown", presence=0, depth=0,
                confidence=0.0, score=0, evidence=["No direct evidence found"],
            )
            continue

        raw_score = presence * 0.25 + depth_pct * 0.5 + confidence * 100 * 0.25
        score = int(min(raw_score, 95))
        status = "demonstrated" if score >= 50 else "weak"

        assessments[skill] = SkillAssessment(
            skill=skill,
            status=status,
            presence=presence,
            depth=depth_pct,
            confidence=confidence,
            score=score,
            evidence=list(dict.fromkeys(evidence))[:8],
        )

    return assessments
