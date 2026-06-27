"""Ontology loader backed by YAML files."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parent / "data"


@lru_cache
def load_yaml(name: str) -> list[dict]:
    file_path = DATA_DIR / name
    if not file_path.exists():
        return []
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    return data or []


def load_skills() -> list[dict]:
    return load_yaml("skills.yaml")


def load_certifications() -> list[dict]:
    return load_yaml("certifications.yaml")


def load_education() -> list[dict]:
    return load_yaml("education.yaml")


def load_industries() -> list[dict]:
    return load_yaml("industries.yaml")


def load_job_families() -> list[dict]:
    return load_yaml("job_families.yaml")
