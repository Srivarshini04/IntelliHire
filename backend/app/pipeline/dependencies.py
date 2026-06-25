"""Phase 4 — Dependency Intelligence."""

from __future__ import annotations

import json
import re
from pathlib import Path

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


def _parse_requirements(text: str) -> set[str]:
    deps: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        name = re.split(r"[<>=!~\[\];]", line)[0].strip()
        if name:
            deps.add(name.lower())
    return deps


def _parse_pyproject(text: str) -> set[str]:
    deps: set[str] = set()
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[project]") or stripped.startswith("[tool.poetry.dependencies]"):
            in_deps = True
            continue
        if stripped.startswith("[") and in_deps:
            in_deps = False
        if in_deps and "=" in stripped:
            name = stripped.split("=")[0].strip().strip('"').strip("'")
            if name and name not in {"python"}:
                deps.add(name.lower())
    return deps


def _parse_package_json(text: str) -> set[str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return set()
    deps: set[str] = set()
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        for name in data.get(section, {}):
            deps.add(name.lower())
    return deps


def _parse_go_mod(text: str) -> set[str]:
    deps: set[str] = set()
    for line in text.splitlines():
        if line.strip().startswith("require "):
            parts = line.split()
            if len(parts) >= 2:
                deps.add(parts[1].split("/")[-1].lower())
        if "\t" in line:
            parts = line.strip().split()
            if len(parts) >= 1:
                deps.add(parts[0].split("/")[-1].lower())
    return deps


def _parse_pom_xml(text: str) -> set[str]:
    deps: set[str] = set()
    for match in re.finditer(r"<artifactId>([^<]+)</artifactId>", text):
        deps.add(match.group(1).lower())
    return deps


def extract_dependencies(repo_path: Path) -> set[str]:
    dependencies: set[str] = set()

    for root, _, files in os_walk(repo_path):
        for fname in files:
            if fname not in DEPENDENCY_FILES:
                continue
            fpath = Path(root) / fname
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            if fname == "requirements.txt" or fname == "requirements-dev.txt":
                dependencies |= _parse_requirements(text)
            elif fname == "pyproject.toml":
                dependencies |= _parse_pyproject(text)
            elif fname == "package.json":
                dependencies |= _parse_package_json(text)
            elif fname == "go.mod":
                dependencies |= _parse_go_mod(text)
            elif fname == "pom.xml":
                dependencies |= _parse_pom_xml(text)

    return dependencies


def os_walk(repo_path: Path):
    import os

    skip = {"node_modules", ".git", ".venv", "venv", "dist", "build"}
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in skip]
        yield root, dirs, files
