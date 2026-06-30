"""Internal types for the reasoning engine — not shared contracts.

Private to ``app.intelligence.reasoning``. Must not be imported by other
workstreams or exposed via ``app.shared``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.shared.enums import Intensity


@dataclass
class MaterialityMap:
    """Role-relative importance keyed by canonical entity_ref or theme.

    Built from RoleDNA only — does not read or mutate CandidateGraph.
    """

    by_entity_ref: dict[str, Intensity] = field(default_factory=dict)
    by_theme: dict[str, Intensity] = field(default_factory=dict)
