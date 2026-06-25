"""Feature hierarchy — depth, complexity, multi-channel evidence confidence."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from app.pipeline.repo_context import RepoContext

# Sub-features measure depth; complexity measures production-readiness signals.
FEATURE_HIERARCHY: dict[str, dict] = {
    "authentication": {
        "label": "Authentication",
        "dependencies": ["pyjwt", "python-jose", "passlib", "bcrypt", "auth0", "next-auth", "passport"],
        "path_hints": ["auth/", "authentication/"],
        "sub_features": {
            "basic_login": {"patterns": [r"\blogin\b", r"\blogout\b", r"sign_in", r"signin"], "label": "Basic login/logout"},
            "jwt": {"patterns": [r"\bjwt\b", r"access_token", r"decode_token", r"jwt\.encode"], "label": "JWT tokens"},
            "oauth": {"patterns": [r"\boauth\b", r"oauth2", r"openid"], "label": "OAuth"},
            "refresh_tokens": {"patterns": [r"refresh_token", r"token_refresh"], "label": "Refresh tokens"},
            "session_revocation": {"patterns": [r"revoke", r"blacklist.*token", r"logout_all"], "label": "Session revocation"},
        },
    },
    "role_based_access_control": {
        "label": "Role Based Access Control",
        "dependencies": ["casbin", "django-guardian"],
        "path_hints": ["rbac", "permissions/", "roles/"],
        "sub_features": {
            "roles": {"patterns": [r"\brole\b", r"has_role", r"user_role"], "label": "Role definitions"},
            "permissions": {"patterns": [r"\bpermission", r"check_permission", r"authorize"], "label": "Permission checks"},
            "permission_matrix": {"patterns": [r"permission_map", r"acl", r"policy"], "label": "Permission matrix"},
        },
    },
    "scheduling": {
        "label": "Scheduling",
        "dependencies": ["celery", "apscheduler", "rq", "huey", "airflow", "prefect"],
        "path_hints": ["scheduler", "cron", "tasks/", "jobs/"],
        "sub_features": {
            "cron": {"patterns": [r"\bcron\b", r"cron_trigger", r"crontab"], "label": "Cron scheduling"},
            "job_queue": {"patterns": [r"\.delay\(", r"apply_async", r"enqueue", r"queue\.add"], "label": "Job queue"},
            "recurring_jobs": {"patterns": [r"periodic", r"beat_schedule", r"interval_trigger"], "label": "Recurring jobs"},
            "retry_logic": {"patterns": [r"retry", r"max_retries", r"autoretry"], "label": "Retry logic"},
            "distributed_workers": {"patterns": [r"celery.*worker", r"worker_pool", r"concurrency"], "label": "Distributed workers"},
        },
    },
    "caching": {
        "label": "Caching",
        "dependencies": ["redis", "memcached", "cachetools", "ioredis"],
        "path_hints": ["cache"],
        "sub_features": {
            "in_memory": {"patterns": [r"@lru_cache", r"cachetools", r"functools\.cache"], "label": "In-memory cache"},
            "distributed_cache": {"patterns": [r"redis\.set", r"redis\.get", r"memcache"], "label": "Distributed cache"},
            "cache_invalidation": {"patterns": [r"invalidate", r"cache_delete", r"expire"], "label": "Cache invalidation"},
        },
    },
    "notifications": {
        "label": "Notifications",
        "dependencies": ["sendgrid", "twilio", "nodemailer"],
        "path_hints": ["notification", "notify", "email/"],
        "sub_features": {
            "email": {"patterns": [r"send_email", r"smtp", r"mailer"], "label": "Email notifications"},
            "push": {"patterns": [r"push_notification", r"fcm", r"firebase.*messaging"], "label": "Push notifications"},
            "sms": {"patterns": [r"send_sms", r"twilio"], "label": "SMS notifications"},
        },
    },
    "payments": {
        "label": "Payments",
        "dependencies": ["stripe", "razorpay", "braintree"],
        "path_hints": ["payment", "billing", "checkout"],
        "sub_features": {
            "checkout": {"patterns": [r"checkout_session", r"create_payment"], "label": "Checkout flow"},
            "subscriptions": {"patterns": [r"subscription", r"billing_cycle"], "label": "Subscriptions"},
            "webhooks": {"patterns": [r"stripe.*webhook", r"payment.*webhook"], "label": "Payment webhooks"},
        },
    },
    "api_design": {
        "label": "API Design",
        "dependencies": ["fastapi", "flask", "django", "express", "nestjs"],
        "path_hints": ["routers/", "routes/", "controllers/", "api/"],
        "sub_features": {
            "rest_endpoints": {"patterns": [r"@app\.(get|post|put|delete)", r"apirouter", r"router\."], "label": "REST endpoints"},
            "validation": {"patterns": [r"basemodel", r"@validator", r"schema\.parse"], "label": "Request validation"},
            "versioning": {"patterns": [r"/v1/", r"api_version", r"versioned"], "label": "API versioning"},
            "openapi": {"patterns": [r"openapi", r"swagger", r"redoc"], "label": "OpenAPI docs"},
        },
    },
    "database_design": {
        "label": "Database Design",
        "dependencies": ["sqlalchemy", "prisma", "typeorm", "alembic", "mongoose"],
        "path_hints": ["models/", "migrations/", "schema"],
        "sub_features": {
            "orm_models": {"patterns": [r"declarative_base", r"relationship\(", r"foreignkey"], "label": "ORM models"},
            "migrations": {"patterns": [r"alembic", r"migration", r"op\.create_table"], "label": "Migrations"},
            "indexing": {"patterns": [r"index=true", r"create_index", r"db_index"], "label": "Indexing"},
        },
    },
    "testing": {
        "label": "Testing",
        "dependencies": ["pytest", "jest", "vitest"],
        "path_hints": ["tests/", "test/", "__tests__/"],
        "sub_features": {
            "unit_tests": {"patterns": [r"def test_", r"it\(", r"describe\("], "label": "Unit tests"},
            "fixtures": {"patterns": [r"@pytest\.fixture", r"beforeeach", r"setup\("], "label": "Test fixtures"},
            "integration_tests": {"patterns": [r"testclient", r"supertest", r"integration"], "label": "Integration tests"},
        },
    },
    "ci_cd": {
        "label": "CI/CD",
        "path_hints": [".github/workflows"],
        "sub_features": {
            "automated_tests": {"patterns": [r"pytest", r"npm test", r"run: test"], "label": "CI test runs"},
            "deploy_pipeline": {"patterns": [r"deploy", r"production", r"release"], "label": "Deploy pipeline"},
        },
    },
    "containerization": {
        "label": "Containerization",
        "path_hints": ["dockerfile", "docker-compose"],
        "sub_features": {
            "dockerfile": {"patterns": [r"^FROM\s+"], "label": "Dockerfile"},
            "compose": {"patterns": [r"services:", r"docker-compose"], "label": "Docker Compose"},
            "orchestration": {"patterns": [r"kubernetes", r"helm", r"k8s"], "label": "Orchestration"},
        },
    },
    "monitoring": {
        "label": "Monitoring",
        "dependencies": ["prometheus-client", "sentry-sdk", "opentelemetry"],
        "path_hints": ["monitoring", "metrics"],
        "sub_features": {
            "metrics": {"patterns": [r"prometheus", r"counter\(", r"histogram"], "label": "Metrics"},
            "error_tracking": {"patterns": [r"sentry", r"capture_exception"], "label": "Error tracking"},
            "health_checks": {"patterns": [r"/health", r"health_check", r"readiness"], "label": "Health checks"},
        },
    },
    "cloud_aws": {
        "label": "AWS Cloud",
        "dependencies": ["boto3", "botocore", "awscli"],
        "path_hints": ["terraform/aws", ".aws/", "cloudformation"],
        "sub_features": {
            "s3": {"patterns": [r"s3_client", r"\.upload_file", r"bucket_name", r"aws\.s3"], "label": "S3 storage"},
            "ec2": {"patterns": [r"ec2_client", r"run_instances", r"ec2\."], "label": "EC2 compute"},
            "lambda": {"patterns": [r"lambda_client", r"awslambda", r"serverless"], "label": "Lambda functions"},
            "iam": {"patterns": [r"iam_client", r"attach_role_policy", r"sts\.assume_role"], "label": "IAM"},
            "terraform_aws": {"patterns": [r"provider\s+\"aws\"", r"terraform.*aws"], "label": "Terraform AWS"},
        },
    },
}


@dataclass
class FeatureResult:
    feature_id: str
    label: str
    detected: bool = False
    confidence: float = 0.0
    depth: float = 0.0
    score: int = 0
    sub_features: dict[str, bool] = field(default_factory=dict)
    complexity: dict[str, bool] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    evidence_channels: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "feature_id": self.feature_id,
            "label": self.label,
            "detected": self.detected,
            "confidence": round(self.confidence, 2),
            "depth": round(self.depth, 2),
            "score": self.score,
            "sub_features": self.sub_features,
            "complexity": self.complexity,
            "evidence": self.evidence,
            "evidence_channels": self.evidence_channels,
        }


def _count_cross_file_hits(ctx: RepoContext, patterns: list[str]) -> int:
    hits = 0
    for path, text in ctx.source_files().items():
        lower = text.lower()
        if any(re.search(p, lower, re.IGNORECASE) for p in patterns):
            hits += 1
    return hits


def _detect_sub_features(combined: str, sub_spec: dict) -> tuple[dict[str, bool], list[str]]:
    found: dict[str, bool] = {}
    evidence: list[str] = []
    for key, meta in sub_spec.items():
        matched = any(re.search(p, combined, re.IGNORECASE | re.MULTILINE) for p in meta["patterns"])
        found[key] = matched
        if matched:
            evidence.append(meta["label"])
    return found, evidence


def detect_features(ctx: RepoContext, dependencies: set[str]) -> dict[str, FeatureResult]:
    combined = ctx.combined_source()
    combined_lower = combined.lower()
    dep_lower = {d.lower() for d in dependencies}
    results: dict[str, FeatureResult] = {}

    for feature_id, spec in FEATURE_HIERARCHY.items():
        result = FeatureResult(feature_id=feature_id, label=spec["label"])
        channels: dict[str, bool] = {"dependency": False, "structure": False, "usage": False, "cross_file": False}
        evidence: list[str] = []

        dep_hits = [d for d in spec.get("dependencies", []) if d in dep_lower]
        if dep_hits:
            channels["dependency"] = True
            evidence.append(f"Dependency: {', '.join(dep_hits[:3])}")

        for hint in spec.get("path_hints", []):
            if ctx.has_path(hint):
                channels["structure"] = True
                evidence.append(f"Project structure: {hint}")
                break

        sub_features, sub_evidence = _detect_sub_features(combined_lower, spec.get("sub_features", {}))
        result.sub_features = sub_features
        result.complexity = {k: v for k, v in sub_features.items()}  # complexity = sub-feature map

        if sub_evidence:
            channels["usage"] = True
            evidence.extend(sub_evidence[:5])

        all_patterns = [p for sf in spec.get("sub_features", {}).values() for p in sf["patterns"]]
        if _count_cross_file_hits(ctx, all_patterns) >= 2:
            channels["cross_file"] = True
            evidence.append("Usage confirmed across multiple files")

        active_subs = sum(1 for v in sub_features.values() if v)
        total_subs = max(len(sub_features), 1)
        result.depth = active_subs / total_subs

        channel_count = sum(channels.values())
        result.evidence_channels = channels
        result.confidence = min(0.25 * channel_count + result.depth * 0.5, 1.0)
        result.detected = channel_count >= 2 or (channels["dependency"] and active_subs >= 1) or active_subs >= 2
        result.score = int(min(result.confidence * 60 + result.depth * 40, 95)) if result.detected else 0
        result.evidence = evidence
        results[feature_id] = result

    return results
