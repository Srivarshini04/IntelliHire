"""Parse dependencies from virtual file map."""

from __future__ import annotations

import json
import re
from pathlib import PurePosixPath

from app.pipeline.dependencies import (
    _parse_go_mod,
    _parse_package_json,
    _parse_pom_xml,
    _parse_pyproject,
    _parse_requirements,
)
from app.pipeline.repo_context import DEPENDENCY_FILES, RepoContext


def extract_dependencies_from_context(ctx: RepoContext) -> set[str]:
    dependencies: set[str] = set()

    for path, text in ctx.files.items():
        name = PurePosixPath(path).name
        if name not in DEPENDENCY_FILES:
            continue
        if name in ("requirements.txt", "requirements-dev.txt"):
            dependencies |= _parse_requirements(text)
        elif name == "pyproject.toml":
            dependencies |= _parse_pyproject(text)
        elif name == "package.json":
            dependencies |= _parse_package_json(text)
        elif name == "go.mod":
            dependencies |= _parse_go_mod(text)
        elif name == "pom.xml":
            dependencies |= _parse_pom_xml(text)

    return dependencies
