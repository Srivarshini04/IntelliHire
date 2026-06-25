"""Phase 3 — GitHubRepository Structure Analysis."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

CODE_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".rb", ".php"}
SKIP_DIRS = {
    ".git",
    ".github",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    "coverage",
    ".pytest_cache",
    "target",
}


@dataclass
class ArchitectureFeatures:
    directories: list[str] = field(default_factory=list)
    code_files: int = 0
    lines_of_code: int = 0
    modules: list[str] = field(default_factory=list)
    has_tests: bool = False
    has_docker: bool = False
    has_ci: bool = False
    top_level_layout: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "directory_count": len(self.directories),
            "code_files": self.code_files,
            "lines_of_code": self.lines_of_code,
            "modules": self.modules,
            "module_count": len(self.modules),
            "has_tests": self.has_tests,
            "has_docker": self.has_docker,
            "has_ci": self.has_ci,
            "top_level_layout": self.top_level_layout,
            "directories": self.directories[:50],
        }


def _is_code_file(path: Path) -> bool:
    return path.suffix.lower() in CODE_EXTENSIONS


def analyze_structure(repo_path: Path) -> ArchitectureFeatures:
    features = ArchitectureFeatures()

    if not repo_path.exists():
        return features

    for entry in sorted(repo_path.iterdir()):
        if entry.name.startswith("."):
            continue
        features.top_level_layout.append(f"{entry.name}/" if entry.is_dir() else entry.name)

    module_names: set[str] = set()
    directories: set[str] = set()

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]

        rel_root = Path(root).relative_to(repo_path)
        if str(rel_root) != ".":
            directories.add(str(rel_root).replace("\\", "/"))

        for name in dirs:
            parts = (rel_root / name).parts
            if len(parts) == 1:
                module_names.add(name)

        for fname in files:
            fpath = Path(root) / fname
            rel = fpath.relative_to(repo_path)
            lower_name = fname.lower()

            if lower_name == "dockerfile" or lower_name.startswith("docker-compose"):
                features.has_docker = True
            if rel.parts[:2] == (".github", "workflows") or lower_name.endswith(".yml"):
                if ".github/workflows" in str(rel).replace("\\", "/"):
                    features.has_ci = True

            if "test" in lower_name or "tests" in str(rel).lower():
                features.has_tests = True

            if _is_code_file(fpath):
                features.code_files += 1
                try:
                    text = fpath.read_text(encoding="utf-8", errors="ignore")
                    features.lines_of_code += text.count("\n") + 1
                except OSError:
                    pass

    features.directories = sorted(directories)
    features.modules = sorted(module_names)
    return features
