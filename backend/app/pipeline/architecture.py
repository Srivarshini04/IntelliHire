"""Phase 5 — Architecture Detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ARCHITECTURE_SIGNALS: dict[str, dict[str, list[str]]] = {
    "database_layer": {
        "dependencies": [
            "sqlalchemy",
            "prisma",
            "typeorm",
            "psycopg2",
            "asyncpg",
            "mongoose",
            "sequelize",
            "django",
            "alembic",
            "knex",
        ],
        "files": ["prisma/schema.prisma", "migrations"],
        "keywords": ["select ", "insert into", "create table", "foreignkey"],
    },
    "auth_layer": {
        "dependencies": [
            "pyjwt",
            "python-jose",
            "passlib",
            "bcrypt",
            "auth0",
            "next-auth",
            "passport",
            "firebase-admin",
        ],
        "files": [],
        "keywords": ["oauth", "jwt", "bearer", "authenticate", "login_required", "session"],
    },
    "background_jobs": {
        "dependencies": ["celery", "rq", "bullmq", "bull", "dramatiq", "huey", "sidekiq"],
        "files": [],
        "keywords": ["@celery", "delay(", "apply_async", "bullmq", "queue"],
    },
    "caching": {
        "dependencies": ["redis", "memcached", "pymemcache", "ioredis"],
        "files": [],
        "keywords": ["cache", "redis", "memcache"],
    },
    "api_layer": {
        "dependencies": [
            "fastapi",
            "flask",
            "django",
            "express",
            "nestjs",
            "spring-boot",
            "gin",
            "fiber",
            "uvicorn",
            "starlette",
        ],
        "files": ["openapi.yaml", "openapi.json", "swagger"],
        "keywords": ["apirouter", "router.get", "app.get(", "@app.route", "restcontroller"],
    },
    "testing": {
        "dependencies": ["pytest", "jest", "vitest", "mocha", "unittest", "playwright", "cypress"],
        "files": ["conftest.py", "jest.config.js", "vitest.config.ts"],
        "keywords": ["def test_", "describe(", "it(", "expect("],
    },
    "devops": {
        "dependencies": [],
        "files": ["dockerfile", "docker-compose.yml", "docker-compose.yaml", ".github/workflows"],
        "keywords": ["deploy", "kubernetes", "terraform", "helm"],
    },
}


@dataclass
class ArchitectureLayers:
    layers: dict[str, bool] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, bool]:
        return dict(self.layers)


def _scan_code_keywords(repo_path: Path, keywords: list[str], limit: int = 3) -> list[str]:
    hits: list[str] = []
    extensions = {".py", ".js", ".ts", ".java", ".go", ".rb"}
    for fpath in repo_path.rglob("*"):
        if not fpath.is_file() or fpath.suffix.lower() not in extensions:
            continue
        if any(p in fpath.parts for p in ("node_modules", ".git", "venv", ".venv")):
            continue
        try:
            text = fpath.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        for kw in keywords:
            if kw.lower() in text:
                hits.append(kw)
                if len(hits) >= limit:
                    return hits
    return hits


def detect_architecture(
    repo_path: Path,
    dependencies: set[str],
    structure_flags: dict | None = None,
) -> ArchitectureLayers:
    structure_flags = structure_flags or {}
    result = ArchitectureLayers()

    for layer, signals in ARCHITECTURE_SIGNALS.items():
        detected = False
        layer_evidence: list[str] = []

        dep_hits = [d for d in signals["dependencies"] if d in dependencies]
        if dep_hits:
            detected = True
            layer_evidence.append(f"dependencies: {', '.join(dep_hits[:5])}")

        for rel_path in signals["files"]:
            candidates = list(repo_path.rglob(Path(rel_path).name if "/" not in rel_path else rel_path))
            if any(p.exists() for p in [repo_path / rel_path] + candidates):
                detected = True
                layer_evidence.append(f"file: {rel_path}")
                break

        if signals["keywords"]:
            kw_hits = _scan_code_keywords(repo_path, signals["keywords"])
            if kw_hits:
                detected = True
                layer_evidence.append(f"patterns: {', '.join(kw_hits[:3])}")

        if layer == "devops":
            if structure_flags.get("has_docker"):
                detected = True
                layer_evidence.append("Docker configuration")
            if structure_flags.get("has_ci"):
                detected = True
                layer_evidence.append("CI/CD workflows")

        if layer == "testing" and structure_flags.get("has_tests"):
            detected = True
            layer_evidence.append("test directory/files")

        result.layers[layer] = detected
        if detected:
            result.evidence.extend(f"{layer}: {e}" for e in layer_evidence)

    return result
