"""PII detection/redaction — Phase 1+."""

import re

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"\+?[\d\s\-().]{10,}")


def detect_pii(text: str) -> dict[str, list[str]]:
  return {
    "emails": EMAIL_RE.findall(text),
    "phones": PHONE_RE.findall(text),
  }
