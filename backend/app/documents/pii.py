"""PII — Detect → Minimize → Configurable Redaction."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.document import PiiDetectionResult, PiiPolicy

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
# Heuristic name: Title Case two-word sequences at line start (resume headers)
NAME_LINE_RE = re.compile(r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s*$", re.MULTILINE)

MASK_TOKENS = {
    "email": "<EMAIL>",
    "phone": "<PHONE>",
    "name": "<CANDIDATE_NAME>",
}


@dataclass
class PiiPipelineResult:
    detection: PiiDetectionResult
    masked_text: str
    original_text: str


def detect_pii(text: str) -> PiiDetectionResult:
    emails = list(dict.fromkeys(EMAIL_RE.findall(text)))
    phones = list(dict.fromkeys(PHONE_RE.findall(text)))
    names = list(dict.fromkeys(NAME_LINE_RE.findall(text)[:3]))  # cap name guesses
    return PiiDetectionResult(emails=emails, phones=phones, names=names)


def mask_pii(text: str, detection: PiiDetectionResult | None = None) -> tuple[str, PiiDetectionResult]:
    """Mask sensitive values. Skills, titles, tech terms unchanged."""
    detection = detection or detect_pii(text)
    masked = text
    count = 0

    for email in detection.emails:
        masked = masked.replace(email, MASK_TOKENS["email"])
        count += 1
    for phone in detection.phones:
        masked = masked.replace(phone, MASK_TOKENS["phone"])
        count += 1
    for name in detection.names:
        masked = re.sub(re.escape(name), MASK_TOKENS["name"], masked)
        count += 1

    detection.masked_count = count
    return masked, detection


def apply_pii_policy(
    original_text: str,
    policy: PiiPolicy,
    *,
    is_external_llm: bool = True,
) -> PiiPipelineResult:
    """
    Three-stage pipeline:
    Extract → Detect → Policy Engine
      - internal model: send original
      - external model: send masked
    """
    detection = detect_pii(original_text)
    masked, detection = mask_pii(original_text, detection)

    if policy == PiiPolicy.DETECT_ONLY:
        return PiiPipelineResult(detection=detection, masked_text=original_text, original_text=original_text)
    if policy == PiiPolicy.MASK_ALWAYS:
        return PiiPipelineResult(detection=detection, masked_text=masked, original_text=original_text)
    # MASK_EXTERNAL (default)
    if is_external_llm:
        return PiiPipelineResult(detection=detection, masked_text=masked, original_text=original_text)
    return PiiPipelineResult(detection=detection, masked_text=original_text, original_text=original_text)
