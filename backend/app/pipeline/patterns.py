"""Phase 6 — Code Pattern Analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

PATTERN_LIBRARY: dict[str, dict[str, list[str]]] = {
    "FastAPI": {
        "routing": [r"APIRouter\s*\(", r"@(?:app|router)\.(?:get|post|put|delete|patch)\s*\("],
        "dependency_injection": [r"Depends\s*\(", r"Security\s*\("],
        "middleware": [r"add_middleware\s*\(", r"@app\.middleware"],
        "background_tasks": [r"BackgroundTasks", r"background_tasks\.add_task"],
        "validation": [r"BaseModel", r"Field\s*\(", r"@validator"],
        "websocket": [r"WebSocket", r"@.*\.websocket\s*\("],
    },
    "PostgreSQL": {
        "orm": [r"create_engine\s*\(", r"declarative_base", r"sessionmaker"],
        "queries": [r"session\.query\s*\(", r"select\s*\(", r"execute\s*\("],
        "migrations": [r"alembic", r"op\.create_table", r"migrations/versions"],
        "async_db": [r"asyncpg", r"AsyncSession", r"create_async_engine"],
    },
    "AWS": {
        "sdk": [r"boto3", r"import\s+boto3", r"from\s+boto3"],
        "services": [r"s3\.|S3Client|s3_client", r"lambda_client|awslambda", r"dynamodb|DynamoDB"],
        "deployment": [r"serverless\.yml", r"cdk", r"cloudformation", r"terraform.*aws"],
        "auth": [r"cognito", r"sts\.client", r"iam\."],
    },
    "Redis": {
        "client": [r"redis\.Redis", r"from\s+redis", r"import\s+redis"],
        "caching": [r"\.setex\s*\(", r"\.get\s*\(", r"cache"],
        "pubsub": [r"publish\s*\(", r"subscribe\s*\(", r"pubsub"],
    },
    "Docker": {
        "dockerfile": [r"^FROM\s+", r"^RUN\s+", r"^CMD\s+", r"^ENTRYPOINT"],
        "compose": [r"services:", r"image:", r"docker-compose"],
    },
    "pytest": {
        "fixtures": [r"@pytest\.fixture", r"conftest"],
        "assertions": [r"assert\s+", r"pytest\.raises"],
        "parametrize": [r"@pytest\.mark\.parametrize"],
    },
    "React": {
        "components": [r"function\s+\w+\s*\([^)]*\)\s*\{", r"export\s+default\s+function"],
        "hooks": [r"useState\s*\(", r"useEffect\s*\(", r"useContext\s*\("],
        "jsx": [r"return\s*\(\s*<", r"<\w+[^>]*>"],
    },
    "Node.js": {
        "express": [r"express\s*\(", r"app\.(get|post|use)\s*\("],
        "middleware": [r"app\.use\s*\(", r"next\s*\("],
        "async": [r"async\s+function", r"await\s+"],
    },
}


@dataclass
class PatternResult:
    skill: str
    patterns_detected: list[str] = field(default_factory=list)
    total_patterns: int = 0
    depth: float = 0.0
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "patterns_detected": self.patterns_detected,
            "total_patterns": self.total_patterns,
            "depth": round(self.depth, 2),
            "evidence": self.evidence,
        }


def _iter_source_files(repo_path: Path) -> list[Path]:
    extensions = {".py", ".js", ".ts", ".tsx", ".jsx", ".yml", ".yaml", ".toml", ".dockerfile"}
    files: list[Path] = []
    skip = {"node_modules", ".git", "venv", ".venv", "dist", "build"}
    for fpath in repo_path.rglob("*"):
        if not fpath.is_file():
            continue
        if any(p in fpath.parts for p in skip):
            continue
        if fpath.name.lower() == "dockerfile" or fpath.suffix.lower() in extensions:
            files.append(fpath)
    return files


def detect_patterns(repo_path: Path, skills: list[str] | None = None) -> dict[str, PatternResult]:
    source_files = _iter_source_files(repo_path)
    combined_text = ""
    file_texts: dict[str, str] = {}

    for fpath in source_files[:200]:
        try:
            text = fpath.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        file_texts[str(fpath.relative_to(repo_path))] = text
        combined_text += text + "\n"

    skills_to_check = skills or list(PATTERN_LIBRARY.keys())
    results: dict[str, PatternResult] = {}

    for skill in skills_to_check:
        patterns = PATTERN_LIBRARY.get(skill)
        if not patterns:
            continue

        result = PatternResult(skill=skill, total_patterns=len(patterns))
        for pattern_name, regexes in patterns.items():
            for regex in regexes:
                if re.search(regex, combined_text, re.MULTILINE | re.IGNORECASE):
                    result.patterns_detected.append(pattern_name)
                    result.evidence.append(f"{pattern_name} ({skill})")
                    break

        if result.total_patterns:
            result.depth = len(set(result.patterns_detected)) / result.total_patterns
        results[skill] = result

    return results
