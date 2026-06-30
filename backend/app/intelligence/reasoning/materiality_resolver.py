"""Resolve role-relative materiality from RoleDNA (Decision B)."""

from __future__ import annotations

from app.intelligence.reasoning.types import MaterialityMap
from app.shared.models import RoleDNA


class MaterialityResolver:
    """Map RoleDNA requirements and behavioural fields to per-entity importance."""

    def resolve(self, role: RoleDNA) -> MaterialityMap:
        """Build a MaterialityMap for the given role.

        TODO: map must_have_skills -> CRITICAL or HIGH
        TODO: map nice_to_have_skills -> LOW
        TODO: derive theme weights from capability_weights and behavioural Intensity fields
        TODO: elevate domain-related entity_refs when role.domain is set
        """
        return MaterialityMap()
