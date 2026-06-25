"""Virtual repository context — files fetched via Tree API, no clone required."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath


CODE_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".rb", ".php", ".sql"}
DEPENDENCY_FILES = {
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "Pipfile",
    "package.json",
    "pom.xml",
    "go.mod",
    "Cargo.toml",
    "Gemfile",
}
INFRA_FILES = {"dockerfile", "docker-compose.yml", "docker-compose.yaml", "makefile"}
README_NAMES = {"readme.md", "readme.rst", "readme.txt"}
SKIP_SEGMENTS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    "coverage",
    ".pytest_cache",
    "target",
    "vendor",
    "images",
    "img",
    "assets",
    "static/media",
    "datasets",
    "data/raw",
    ".terraform",
}


@dataclass
class RepoContext:
    full_name: str
    default_branch: str
    tree_paths: list[str] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)

    def has_path(self, fragment: str) -> bool:
        fragment = fragment.lower()
        return any(fragment in p.lower() for p in self.tree_paths)

    def paths_matching(self, suffix: str) -> list[str]:
        suffix = suffix.lower()
        return [p for p in self.tree_paths if p.lower().endswith(suffix)]

    def read(self, path: str) -> str | None:
        return self.files.get(path)

    def combined_source(self, max_files: int = 200) -> str:
        parts: list[str] = []
        for path in sorted(self.files):
            if _is_source_path(path):
                parts.append(self.files[path])
                if len(parts) >= max_files:
                    break
        return "\n".join(parts)

    def dependency_file_contents(self) -> dict[str, str]:
        return {p: c for p, c in self.files.items() if PurePosixPath(p).name in DEPENDENCY_FILES}

    def source_files(self) -> dict[str, str]:
        return {p: c for p, c in self.files.items() if _is_source_path(p)}


def _is_source_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    if any(seg in SKIP_SEGMENTS for seg in parts):
        return False
    name = PurePosixPath(path).name.lower()
    if name in INFRA_FILES or name in README_NAMES:
        return True
    return PurePosixPath(path).suffix.lower() in CODE_EXTENSIONS


def should_fetch_path(path: str) -> bool:
    """Decide whether a tree path is worth fetching via Blob API."""
    p = PurePosixPath(path)
    parts = p.parts
    if any(seg in SKIP_SEGMENTS for seg in parts):
        return False

    name = p.name.lower()
    if name in DEPENDENCY_FILES or name in INFRA_FILES or name in README_NAMES:
        return True
    if name == "dockerfile":
        return True
    if ".github/workflows" in path.replace("\\", "/"):
        return True

    suffix = p.suffix.lower()
    if suffix in CODE_EXTENSIONS:
        # Prefer application code directories; still fetch top-level source
        depth = len(parts)
        if depth <= 6:
            return True
        app_segments = {"app", "src", "lib", "api", "services", "routers", "models", "tests", "test"}
        if any(seg in app_segments for seg in parts):
            return True
    return False
