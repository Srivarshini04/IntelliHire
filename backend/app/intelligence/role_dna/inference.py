"""Deterministic Role DNA inference helpers.

Pure functions — no I/O, no LLM, no randomness. They turn RoleBlueprint signals
into the semantic Intensity levels and summaries that make up a RoleDNA. The same
input always yields the same output.
"""

from __future__ import annotations

import re
from typing import Any

from app.shared.enums import EvidenceSource, Intensity

INTENSITY_ORDER: list[Intensity] = [
    Intensity.NONE,
    Intensity.LOW,
    Intensity.MEDIUM,
    Intensity.HIGH,
    Intensity.CRITICAL,
]


def max_intensity(a: Intensity, b: Intensity) -> Intensity:
    """Return the stronger of two Intensity values."""
    return a if INTENSITY_ORDER.index(a) >= INTENSITY_ORDER.index(b) else b


# --- value extraction from a (possibly ExtractedField/SkillField-shaped) dict ---

def field_value(raw: Any) -> Any:
    """Unwrap an ExtractedField/SkillField-shaped dict to its scalar value."""
    if isinstance(raw, dict):
        for key in ("value", "normalized_name", "canonical_name", "name"):
            if raw.get(key) is not None:
                return raw[key]
        return None
    return raw


def value_list(raw: Any) -> list[str]:
    """Unwrap a list of ExtractedField/SkillField dicts (or plain strings) to strings."""
    if not raw:
        return []
    out: list[str] = []
    for item in raw:
        v = field_value(item)
        if v is not None:
            out.append(str(v))
    return out


# --- engineering level ---

_LEVEL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "staff": ("staff", "principal", "lead engineer", "architect", "head of", "director"),
    "senior": ("senior", "sr.", "sr ", "experienced"),
    "junior": ("junior", "jr.", "jr ", "entry", "intern", "graduate", "fresher", "trainee"),
}


def _first_int(text: str) -> int | None:
    m = re.search(r"\d+", text)
    return int(m.group()) if m else None


def normalize_engineering_level(experience_level: str | None) -> str | None:
    """Map a free-text experience descriptor to junior|mid|senior|staff."""
    if not experience_level:
        return None
    text = experience_level.strip().lower()
    for level, kws in _LEVEL_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return level
    years = _first_int(text)
    if years is not None:
        if years < 2:
            return "junior"
        if years < 5:
            return "mid"
        if years < 8:
            return "senior"
        return "staff"
    return "mid"


def seniority_floor(level: str | None) -> Intensity:
    """Senior+ roles imply a baseline ownership/communication floor."""
    return {"staff": Intensity.HIGH, "senior": Intensity.MEDIUM}.get(level or "", Intensity.LOW)


# --- intensity inference ---

_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ownership": ("own", "ownership", "independent", "end-to-end", "end to end", "drive",
                  "autonom", "self-directed", "accountable"),
    "learning": ("learn", "adapt", "fast-paced", "evolving", "pick up", "curious", "new technolog"),
    "collaboration": ("collaborat", "cross-functional", "cross functional", "team",
                      "stakeholder", "partner", "work with"),
    "research": ("research", "novel", "paper", "experiment", "prototype", "state-of-the-art",
                 "sota", "publication", "r&d"),
    "delivery": ("deliver", "ship", "deadline", "production", "release", "on time", "execution"),
    "architecture": ("architect", "scal", "distributed", "system design", "design system",
                     "microservice", "infrastructure", "high availability", "throughput"),
    "communication": ("communicat", "present", "write", "document", "stakeholder", "articulate", "explain"),
    "ambiguity": ("ambiguity", "ambiguous", "uncertain", "startup", "0 to 1", "0-to-1",
                  "undefined", "greenfield", "fast-changing"),
    "leadership": ("lead", "mentor", "manage", "coach", "guide", "team lead", "leadership"),
}


def _count_hits(text: str, kws: tuple[str, ...]) -> int:
    return sum(1 for kw in kws if kw in text)


def _intensity_from_count(n: int) -> Intensity:
    if n >= 3:
        return Intensity.CRITICAL
    if n == 2:
        return Intensity.HIGH
    if n == 1:
        return Intensity.MEDIUM
    return Intensity.LOW


def infer_intensity(signal_text: str, dimension: str, *, floor: Intensity = Intensity.LOW) -> Intensity:
    """Deterministically infer an Intensity for a behavioural dimension from signal text."""
    level = _intensity_from_count(_count_hits(signal_text.lower(), _KEYWORDS.get(dimension, ())))
    return max_intensity(level, floor)


def weights_architecture_floor(weights: dict[str, float]) -> Intensity:
    """A heavy system-design capability weight implies a HIGH architecture expectation."""
    for k, v in (weights or {}).items():
        kl = str(k).lower()
        if ("system" in kl or "architect" in kl or "design" in kl) and v >= 0.25:
            return Intensity.HIGH
    return Intensity.LOW


def risk_tolerance(level: str | None, ambiguity: Intensity) -> Intensity:
    """Higher ambiguity and seniority imply more hiring risk tolerance."""
    base = INTENSITY_ORDER.index(ambiguity)
    if level in ("senior", "staff"):
        base += 1
    base = max(0, min(len(INTENSITY_ORDER) - 1, base))
    return INTENSITY_ORDER[base]


# --- required evidence mapping ---

def map_required_evidence(values: list[str]) -> list[EvidenceSource]:
    out: list[EvidenceSource] = []
    for v in values:
        try:
            out.append(EvidenceSource(str(v).strip().lower()))
        except ValueError:
            continue
    return out


# --- summary / success profile / interview focus synthesis ---

def synthesize_summary(
    role_title: str | None, level: str | None, domain: str | None,
    must_have: list[str], responsibilities: list[str],
) -> str:
    title = role_title or "Engineer"
    lvl = f"{level} " if level else ""
    dom = f" in {domain}" if domain else ""
    skills = ", ".join(must_have[:5]) if must_have else "core engineering skills"
    summary = f"{lvl}{title}{dom} focused on {skills}."
    if responsibilities:
        summary += f" Key responsibility: {responsibilities[0].rstrip('.')}."
    return summary.strip()


def synthesize_success_profile(must_have: list[str], key_dims: dict[str, Intensity]) -> str:
    strong = [d for d, i in key_dims.items() if i in (Intensity.HIGH, Intensity.CRITICAL)]
    parts: list[str] = []
    if must_have:
        parts.append("demonstrable depth in " + ", ".join(must_have[:4]))
    if strong:
        parts.append("strong " + ", ".join(strong))
    if not parts:
        return "Succeeds by reliably delivering on the role's core responsibilities."
    return "Succeeds with " + "; ".join(parts) + "."


def build_interview_focus(must_have: list[str], key_dims: dict[str, Intensity]) -> list[str]:
    label = {
        "architecture": "system design", "ownership": "end-to-end ownership",
        "research": "research/experimentation", "leadership": "leadership/mentoring",
        "communication": "communication", "delivery": "delivery under deadlines",
    }
    focus = [f"Validate hands-on depth in {skill}" for skill in must_have[:3]]
    focus += [
        f"Probe {label.get(dim, dim)}"
        for dim, i in key_dims.items()
        if i in (Intensity.HIGH, Intensity.CRITICAL)
    ]
    return focus[:6]
