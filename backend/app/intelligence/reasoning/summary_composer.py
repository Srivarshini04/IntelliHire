"""Compose recruiter-friendly reasoning summaries from structured reasoning outputs.

Pure read-only composition — no new reasoning, scoring, gap/uncertainty detection, or mutation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.intelligence.reasoning.confidence_engine import ConfidenceResult
from app.intelligence.reasoning.gap_analyzer import GapAnalysis, GapItem
from app.intelligence.reasoning.uncertainty_detector import UncertaintyAnalysis, UncertaintyItem
from app.shared.enums import Intensity
from app.shared.models import ReasoningClaim

_MAX_SECTION_ITEMS = 5
_MAX_LINE_LENGTH = 80
_INTENSITY_RANK = {
    Intensity.CRITICAL: 4,
    Intensity.HIGH: 3,
    Intensity.MEDIUM: 2,
    Intensity.LOW: 1,
    Intensity.NONE: 0,
}
_GAP_SEVERITY_RANK = {"critical": 3, "moderate": 2, "minor": 1}
_UNCERTAINTY_SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}

_PRETTY_NAMES: dict[str, str] = {
    "skill:vector_search": "Vector Search",
    "skill:learning_to_rank": "Learning to Rank",
    "skill:ranking_evaluation": "Ranking Evaluation",
    "skill:llm_finetuning": "LLM Fine-tuning",
    "skill:hr_tech_domain": "HR Technology",
    "skill:kubernetes": "Kubernetes",
    "skill:python": "Python",
    "skill:fastapi": "FastAPI",
    "skill:docker": "Docker",
    "skill:embeddings_retrieval": "Embedding-based Retrieval",
    "activity:commit_cadence": "Engineering Activity",
    "domain:talent_intelligence_search_ranking": "Search & Ranking Domain",
}

_CLAIM_LABELS: dict[str, str] = {
    "claim_retrieval": "Embedding-based Retrieval",
    "claim_python": "Python & FastAPI",
    "claim_eval": "Ranking Evaluation",
    "claim_availability": "Availability & Activity",
    "claim_finetuning": "LLM Fine-tuning",
}


@dataclass(frozen=True)
class ReasoningSummary:
    """Recruiter-facing summary derived from prior reasoning stages."""

    strengths: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    confidence_text: str = ""
    overall_summary: str = ""


def _pretty_name(value: str) -> str:
    """Convert internal entity ids into recruiter-friendly labels."""
    key = value.strip()
    if key in _PRETTY_NAMES:
        return _PRETTY_NAMES[key]
    if key in _CLAIM_LABELS:
        return _CLAIM_LABELS[key]
    if ":" in key:
        slug = key.split(":", 1)[1]
        return slug.replace("_", " ").title()
    return key


def _truncate(text: str, limit: int = _MAX_LINE_LENGTH) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _humanize_text(text: str) -> str:
    """Replace internal identifiers embedded in free text."""
    output = text

    def _replace(match: re.Match[str]) -> str:
        return _pretty_name(match.group(0))

    output = re.sub(r"\b(?:skill|activity|domain|repo):[a-z0-9_]+\b", _replace, output)
    output = output.replace("must have", "must-have")
    output = output.replace("nice to have", "nice-to-have")
    return _truncate(output)


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
    return out


def _limit_items(items: list[str], limit: int = _MAX_SECTION_ITEMS) -> list[str]:
    return items[:limit]


def _is_strength_claim(claim: ReasoningClaim) -> bool:
    if not claim.supporting_evidence_ids:
        return False
    if claim.counter_evidence_ids and len(claim.counter_evidence_ids) >= len(
        claim.supporting_evidence_ids
    ):
        return False
    return True


def _claim_sort_key(claim: ReasoningClaim) -> tuple[int, float, str]:
    return (
        -_INTENSITY_RANK.get(claim.materiality, 0),
        -claim.confidence,
        claim.claim_id,
    )


def _strength_label(claim: ReasoningClaim) -> str:
    if claim.claim_id in _CLAIM_LABELS:
        return _CLAIM_LABELS[claim.claim_id]
    if claim.entity_refs:
        names = [_pretty_name(ref) for ref in claim.entity_refs[:2]]
        return " & ".join(names)
    return _truncate(claim.statement.strip() or claim.conclusion.strip())


def _compose_strengths(claims: list[ReasoningClaim]) -> list[str]:
    candidates = sorted(
        [claim for claim in claims if _is_strength_claim(claim)],
        key=_claim_sort_key,
    )
    lines = [claim.conclusion.strip() or claim.statement.strip() for claim in candidates]
    return _limit_items(_dedupe_preserve_order(lines))


def _compose_strength_bullets(claims: list[ReasoningClaim]) -> list[str]:
    candidates = sorted(
        [claim for claim in claims if _is_strength_claim(claim)],
        key=_claim_sort_key,
    )
    bullets: list[str] = []
    for claim in candidates:
        label = _strength_label(claim)
        detail = _humanize_text(claim.conclusion.strip() or claim.statement.strip())
        if detail.lower() == label.lower():
            bullets.append(label)
        elif detail:
            bullets.append(f"{label}: {_truncate(detail, 60)}")
        else:
            bullets.append(label)
    return _limit_items(_dedupe_preserve_order(bullets))


def _gap_sort_key(item: GapItem) -> tuple[int, str]:
    return (-_GAP_SEVERITY_RANK.get(item.severity, 0), item.title.lower())


def _gap_bullet(item: GapItem) -> str:
    title = _pretty_name(item.title)
    for ref in item.missing_evidence:
        if ":" in ref and not ref.startswith(("supporting_", "corroboration")):
            title = _pretty_name(ref)
            break

    if item.severity == "critical" and title:
        lowered = item.rationale.lower()
        if "no substantiating" in lowered or "no supporting" in lowered:
            return f"Missing production {title} experience"
        return f"{title} experience missing"

    if item.rationale.strip():
        humanized = _humanize_text(item.rationale)
        if title and title.lower() in humanized.lower():
            return humanized
        if title:
            return f"{title}: {_truncate(humanized, 60)}"
        return humanized

    if title:
        return f"{title} exposure limited"
    return "Gap identified"


def _compose_gaps(gap_analysis: GapAnalysis) -> list[str]:
    items = sorted(gap_analysis.all_items(), key=_gap_sort_key)
    lines = [item.rationale.strip() or item.title.strip() for item in items]
    return _limit_items(_dedupe_preserve_order(lines))


def _compose_gap_bullets(gap_analysis: GapAnalysis) -> list[str]:
    items = sorted(gap_analysis.all_items(), key=_gap_sort_key)
    return _limit_items(_dedupe_preserve_order([_gap_bullet(item) for item in items]))


def _uncertainty_sort_key(item: UncertaintyItem) -> tuple[int, str]:
    return (-_UNCERTAINTY_SEVERITY_RANK.get(item.severity, 0), item.title.lower())


def _uncertainty_bullet(item: UncertaintyItem) -> str:
    if item.rationale.strip():
        return _humanize_text(item.rationale)
    title = _pretty_name(item.title)
    return title or "Uncertainty identified"


def _compose_uncertainties(uncertainty_analysis: UncertaintyAnalysis) -> list[str]:
    items = sorted(uncertainty_analysis.all_items(), key=_uncertainty_sort_key)
    lines = [item.rationale.strip() or item.title.strip() for item in items]
    return _limit_items(_dedupe_preserve_order(lines))


def _compose_uncertainty_bullets(uncertainty_analysis: UncertaintyAnalysis) -> list[str]:
    items = sorted(uncertainty_analysis.all_items(), key=_uncertainty_sort_key)
    return _limit_items(_dedupe_preserve_order([_uncertainty_bullet(item) for item in items]))


def _confidence_level_label(overall: float) -> str:
    if overall >= 0.75:
        return "High"
    if overall >= 0.55:
        return "Moderate"
    return "Low"


def _compose_confidence_text(confidence: ConfidenceResult) -> str:
    level = _confidence_level_label(confidence.overall_confidence).lower()
    pct = round(confidence.overall_confidence * 100, 2)
    return (
        f"Overall reasoning confidence is {confidence.overall_confidence:.2f} ({level}). "
        f"Overall confidence: {pct:.2f}% ({_confidence_level_label(confidence.overall_confidence)}). "
        f"{confidence.explanation.strip()}"
    )


def _bullet_section(title: str, items: list[str]) -> list[str]:
    if not items:
        return []
    lines = [title]
    lines.extend(f"• {item}" for item in items)
    lines.append("")
    return lines


def _compose_overall_summary(
    strength_bullets: list[str],
    gap_bullets: list[str],
    uncertainty_bullets: list[str],
    confidence: ConfidenceResult,
    confidence_text: str,
) -> str:
    if not strength_bullets and not gap_bullets and not uncertainty_bullets:
        return confidence_text

    lines: list[str] = ["Summary", ""]

    lines.extend(_bullet_section("Strengths", strength_bullets))
    lines.extend(_bullet_section("Gaps to probe", gap_bullets))
    lines.extend(_bullet_section("Uncertainties", uncertainty_bullets))

    pct = round(confidence.overall_confidence * 100, 2)
    level = _confidence_level_label(confidence.overall_confidence)
    lines.append("Confidence")
    lines.append(f"Overall confidence: {pct:.2f}% ({level})")

    return "\n".join(lines).strip()


class SummaryComposer:
    """Turn structured reasoning artifacts into recruiter-readable summary text."""

    def compose(
        self,
        claims: list[ReasoningClaim],
        gaps: GapAnalysis,
        uncertainties: UncertaintyAnalysis,
        confidence: ConfidenceResult,
    ) -> ReasoningSummary:
        """Build a summary without mutating inputs."""
        strengths = _compose_strengths(claims)
        gap_lines = _compose_gaps(gaps)
        uncertainty_lines = _compose_uncertainties(uncertainties)
        confidence_text = _compose_confidence_text(confidence)
        overall_summary = _compose_overall_summary(
            _compose_strength_bullets(claims),
            _compose_gap_bullets(gaps),
            _compose_uncertainty_bullets(uncertainties),
            confidence,
            confidence_text,
        )

        return ReasoningSummary(
            strengths=strengths,
            gaps=gap_lines,
            uncertainties=uncertainty_lines,
            confidence_text=confidence_text,
            overall_summary=overall_summary,
        )
