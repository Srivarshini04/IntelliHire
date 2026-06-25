"""JD Blueprint Generator — Document → RoleBlueprint via LLM. Phase 2 implementation."""

from __future__ import annotations

from app.llm.factory import get_llm_provider
from app.schemas.document import Document
from app.schemas.job import RoleBlueprint


async def generate_blueprint(document: Document) -> RoleBlueprint:
  """TODO Phase 2: prompt + SkillNormalizer + versioning."""
  raise NotImplementedError("Blueprint generator — implement in feat/jd-intelligence")
