"""Analyze repository structure from virtual file map."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from app.pipeline.repo_context import CODE_EXTENSIONS, RepoContext, SKIP_SEGMENTS


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


def analyze_structure_from_context(ctx: RepoContext) -> ArchitectureFeatures:
    features = ArchitectureFeatures()
    top_level: set[str] = set()
    directories: set[str] = set()
    modules: set[str] = set()

    for path in ctx.tree_paths:
        parts = PurePosixPath(path).parts
        if parts and parts[0] not in SKIP_SEGMENTS:
            top_level.add(parts[0] + ("/" if len(parts) > 1 else ""))
        if len(parts) > 1:
            directories.add("/".join(parts[:-1]))
            if len(parts) == 2:
                modules.add(parts[0])

        lower = path.lower()
        if "test" in lower:
            features.has_tests = True
        if "dockerfile" in lower or "docker-compose" in lower:
            features.has_docker = True
        if ".github/workflows" in lower:
            features.has_ci = True

    for path, content in ctx.files.items():
        suffix = PurePosixPath(path).suffix.lower()
        name = PurePosixPath(path).name.lower()
        if suffix in CODE_EXTENSIONS or name in {"dockerfile"}:
            features.code_files += 1
            features.lines_of_code += content.count("\n") + 1

    features.top_level_layout = sorted(top_level)
    features.directories = sorted(directories)
    features.modules = sorted(modules)
    return features
