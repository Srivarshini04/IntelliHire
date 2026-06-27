"""Canonical knowledge layer for skill normalization and ontology lookups."""

from app.knowledge.normalizer import CanonicalSkill, normalize_skill_hit, normalize_skill_name

__all__ = ["CanonicalSkill", "normalize_skill_hit", "normalize_skill_name"]
