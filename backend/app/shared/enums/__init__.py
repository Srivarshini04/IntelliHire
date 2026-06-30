"""Shared enumerations for DELULU v2 — the controlled vocabularies every module agrees on.

String-valued so they serialize cleanly to JSON / JSONB and round-trip through the
API + DB layers. ``ConfidenceLevel`` is re-exported from the existing
``app.schemas.fields`` (reuse, not redefine).

Public names (authoritative): EvidenceSource, EvidencePolarity, EvidenceType,
VerificationStatus, ConfidenceLevel, RecommendationLevel, RecommendationAction,
GraphNodeType, GraphEdgeType, Intensity, RankingStage, GapSeverity.
"""

from __future__ import annotations

from enum import Enum

# Reuse the existing confidence band enum — do NOT define a competing one.
from app.schemas.fields import ConfidenceLevel  # noqa: F401  (re-exported)


class EvidenceSource(str, Enum):
    """Where a piece of evidence came from.

    Values MUST match the keys in ``app.shared.constants.SOURCE_WEIGHTS``.
    """

    RESUME = "resume"
    GITHUB = "github"
    LINKEDIN = "linkedin"
    LEETCODE = "leetcode"
    PORTFOLIO = "portfolio"
    KAGGLE = "kaggle"
    HUGGINGFACE = "huggingface"
    GITLAB = "gitlab"
    REDROB = "redrob"   # the challenge dataset's pre-structured signals
    MANUAL = "manual"   # recruiter-entered / human-verified


class EvidencePolarity(str, Enum):
    """Whether evidence supports or contradicts its claim (DECISION A).

    Contradictions are RECORDED here but never arithmetically subtracted during
    fusion (fusion is monotonic over SUPPORTS). The ReasoningEngine — and only it —
    resolves SUPPORTS-vs-CONTRADICTS.
    """

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"


class EvidenceType(str, Enum):
    """The category of fact an Evidence object represents.

    GraphBuilder maps (EvidenceType -> GraphNodeType + GraphEdgeType). Providers
    classify *what kind of observed fact* this is; they never assert absence
    (DECISION C — missing requirements are computed downstream in reasoning).
    """

    SKILL = "skill"
    TOOL = "tool"
    PROJECT = "project"
    REPOSITORY = "repository"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    CERTIFICATION = "certification"
    ACHIEVEMENT = "achievement"
    PUBLICATION = "publication"
    CONTRIBUTION = "contribution"
    ASSESSMENT = "assessment"   # e.g. Redrob skill_assessment_scores, LeetCode
    ACTIVITY = "activity"       # e.g. github_activity_score, commit cadence
    DOMAIN = "domain"


class VerificationStatus(str, Enum):
    """Lifecycle of an evidence claim as corroboration accumulates."""

    UNVERIFIED = "unverified"      # single-source, not yet cross-checked
    CORROBORATED = "corroborated"  # multiple independent sources agree
    CONTRADICTED = "contradicted"  # at least one source disagrees
    VERIFIED = "verified"          # human-confirmed


class RecommendationLevel(str, Enum):
    """Graded hiring recommendation — the output label of the DecisionEngine."""

    STRONG_HIRE = "strong_hire"
    HIRE = "hire"
    LEAN_HIRE = "lean_hire"
    NO_HIRE = "no_hire"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class RecommendationAction(str, Enum):
    """Suggested recruiter next action attached to a Recommendation."""

    FAST_TRACK = "fast_track"
    INTERVIEW = "interview"
    HOLD = "hold"
    REJECT = "reject"


class GraphNodeType(str, Enum):
    """Node kinds in the Candidate Graph."""

    CANDIDATE = "candidate"
    SKILL = "skill"
    PROJECT = "project"
    REPOSITORY = "repository"
    ORGANIZATION = "organization"
    ROLE = "role"
    EDUCATION = "education"
    CERTIFICATION = "certification"
    ACHIEVEMENT = "achievement"
    PUBLICATION = "publication"
    DOMAIN = "domain"
    CONTRIBUTION = "contribution"
    TECHNOLOGY = "technology"  # a concrete tool/library/framework (e.g. FastAPI, Postgres)


class GraphEdgeType(str, Enum):
    """Relationship kinds between Candidate Graph nodes."""

    HAS_SKILL = "has_skill"
    USED_IN = "used_in"
    BUILT = "built"
    CONTRIBUTED_TO = "contributed_to"
    WORKED_AT = "worked_at"
    STUDIED_AT = "studied_at"
    HOLDS = "holds"
    IN_DOMAIN = "in_domain"
    DEPLOYED_WITH = "deployed_with"
    PART_OF = "part_of"
    # Graph-intelligence inference edges (added by the RelationshipInferenceEngine).
    USES = "uses"              # repository/project -> technology
    PROVES = "proves"          # repository/project -> skill (demonstrated artefact)
    VALIDATES = "validates"    # certification/assessment -> skill (third-party check)
    ACHIEVED = "achieved"      # candidate -> achievement
    RELATED_TO = "related_to"  # generic co-occurrence / inferred association


class Intensity(str, Enum):
    """Qualitative requirement / signal level (RoleDNA behavioural fields, materiality)."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RankingStage(str, Enum):
    """Which stage of the two-stage funnel produced a ranking row.

    100k candidates -> top 100 forces coarse-to-fine:
      RETRIEVAL = cheap, vectorized, deterministic over the full pool (no LLM).
      RERANK    = expensive reasoning over the shortlist (the submitted 100).
    """

    RETRIEVAL = "retrieval"
    RERANK = "rerank"


class GapSeverity(str, Enum):
    """How damaging a missing/absent-but-required signal is for the role."""

    MINOR = "minor"
    MODERATE = "moderate"
    BLOCKING = "blocking"


__all__ = [
    "EvidenceSource",
    "EvidencePolarity",
    "EvidenceType",
    "VerificationStatus",
    "ConfidenceLevel",
    "RecommendationLevel",
    "RecommendationAction",
    "GraphNodeType",
    "GraphEdgeType",
    "Intensity",
    "RankingStage",
    "GapSeverity",
]
