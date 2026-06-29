"""
DELULU v2 shared foundation.

Single source of truth for cross-module contracts. Every developer imports from
here; nothing redefines these types locally.

    from app.shared.models import Evidence, CandidateGraph, RoleDNA, HiringDecision
    from app.shared.interfaces import EvidenceProvider, ReasoningEngine
    from app.shared.enums import SourceType, Polarity

Stability contract: changes to `app.shared` are breaking changes for all four
workstreams. Treat edits here as protocol changes — announce in the team channel
and bump nothing else until merged.
"""
