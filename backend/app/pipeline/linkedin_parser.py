"""Parse LinkedIn profile text into claims (not skills)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Map natural language → feature labels (same as FEATURE_HIERARCHY labels)
FEATURE_CLAIM_PATTERNS: dict[str, list[str]] = {
    "Authentication": [r"authentication", r"\bjwt\b", r"\boauth\b", r"login system", r"sign[- ]?in"],
    "Role Based Access Control": [r"\brbac\b", r"role[- ]based", r"permission", r"authorization"],
    "Scheduling": [r"scheduling", r"\bappointment", r"\bcron\b", r"job queue", r"background job"],
    "Caching": [r"\bcaching\b", r"\bredis\b", r"cache layer"],
    "Notifications": [r"notification", r"email service", r"push notification", r"\bsms\b"],
    "Payments": [r"\bpayment", r"\bstripe\b", r"billing", r"checkout"],
    "API Design": [r"\bapi\b", r"rest api", r"backend service", r"microservice"],
    "Database Design": [r"database design", r"\bpostgresql\b", r"schema design", r"\bsql\b"],
    "CI/CD": [r"\bci/?cd\b", r"deployment pipeline", r"github actions"],
    "Containerization": [r"\bdocker\b", r"container", r"kubernetes", r"\bk8s\b"],
    "Monitoring": [r"monitoring", r"observability", r"\bsentry\b", r"prometheus"],
    "AWS Cloud": [r"\baws\b", r"amazon web services", r"\bs3\b", r"\bec2\b", r"\blambda\b", r"cloud infrastructure"],
}

SKILL_CLAIM_PATTERNS: dict[str, list[str]] = {
    "FastAPI": [r"\bfastapi\b", r"fast api"],
    "PostgreSQL": [r"\bpostgresql\b", r"\bpostgres\b"],
    "AWS": [r"\baws\b", r"\bamazon web services\b", r"\bboto3\b"],
    "Redis": [r"\bredis\b"],
    "Docker": [r"\bdocker\b"],
    "React": [r"\breact\b", r"reactjs"],
    "Node.js": [r"\bnode\.?js\b", r"\bexpress\b"],
}

OWNERSHIP_PATTERNS = [
    (r"\b(lead|led|leading)\b", "Team Lead"),
    (r"\b(founded|built from scratch|created)\b", "Individual"),
    (r"\b(contributor|contributed|member of)\b", "Contributor"),
]


@dataclass
class LinkedInExtraction:
    features: list[str] = field(default_factory=list)
    feature_evidence: dict[str, list[str]] = field(default_factory=dict)
    skill_claims: list[str] = field(default_factory=list)
    scale: dict[str, int | str] = field(default_factory=dict)
    ownership: str = "Unknown"
    production: bool = False
    experiences: list[dict] = field(default_factory=list)
    extraction_source: str = "heuristic"

    def to_dict(self) -> dict:
        return {
            "features": self.features,
            "feature_evidence": self.feature_evidence,
            "skill_claims": self.skill_claims,
            "scale": self.scale,
            "ownership": self.ownership,
            "production": self.production,
            "experiences": self.experiences,
            "extraction_source": self.extraction_source,
        }


def parse_linkedin_profile(text: str) -> LinkedInExtraction:
    lower = text.lower()
    result = LinkedInExtraction()

    for label, patterns in FEATURE_CLAIM_PATTERNS.items():
        hits = [p for p in patterns if re.search(p, lower)]
        if hits:
            result.features.append(label)
            result.feature_evidence[label] = [f"LinkedIn mentions: {label.lower()}"]

    for skill, patterns in SKILL_CLAIM_PATTERNS.items():
        if any(re.search(p, lower) for p in patterns):
            result.skill_claims.append(skill)

    user_match = re.search(r"(\d[\d,]+)\s*(?:\+)?\s*users", lower)
    if user_match:
        result.scale["users"] = int(user_match.group(1).replace(",", ""))

    req_match = re.search(r"(\d[\d,]+)\s*(?:\+)?\s*(?:requests|req)/", lower)
    if req_match:
        result.scale["requests_per_day"] = int(req_match.group(1).replace(",", ""))

    for pattern, level in OWNERSHIP_PATTERNS:
        if re.search(pattern, lower):
            result.ownership = level
            break

    result.production = bool(re.search(
        r"production|deployed|live system|serving|in production|customers",
        lower,
    ))

    # Split rough experience blocks by common LinkedIn section markers
    for block in re.split(r"\n{2,}|(?:^|\n)(?:experience|projects)\b", text, flags=re.I)[:6]:
        block = block.strip()
        if len(block) < 40:
            continue
        block_features = [f for f in result.features if f.lower() in block.lower() or any(
            re.search(p, block.lower()) for p in FEATURE_CLAIM_PATTERNS.get(f, [])
        )]
        if block_features:
            result.experiences.append({
                "snippet": block[:200],
                "features": block_features,
                "production": "production" in block.lower() or "serving" in block.lower(),
            })

    return result
