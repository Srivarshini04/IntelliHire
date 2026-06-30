"""Entity Resolution Engine — normalize, alias-map, and de-duplicate entities.

Turns the heterogeneous, dirty entity references coming off different sources
("JS", "Node", "Postgres", "amazon") into stable canonical graph entities
("skill:javascript", "skill:node.js", "tech:postgresql", "org:amazon-web-services").

Three layers, cheapest first:
  1. **Exact / alias** — the curated knowledge base (``app.knowledge``) + a built-in
     alias table for orgs and common technologies.
  2. **Semantic normalization** — canonical-name lookup via the skill ontology.
  3. **Fuzzy** — stdlib ``difflib`` ratio against known canonical names, gated by a
     similarity threshold, for typos / spacing variants the alias table misses.

No external fuzzy-match dependency is required (rapidfuzz is optional and not
assumed installed). Resolution is deterministic and side-effect free.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache

from app.knowledge.normalizer import normalize_skill_hit
from app.shared.enums import EvidenceType, GraphEdgeType, GraphNodeType

logger = logging.getLogger(__name__)

# Minimum difflib similarity ratio to accept a fuzzy canonical match.
FUZZY_THRESHOLD = 0.86

# --- alias tables (extend freely; the knowledge base covers most skills) -------
ORG_ALIASES: dict[str, str] = {
    "amazon": "Amazon Web Services",
    "aws": "Amazon Web Services",
    "amazon web services": "Amazon Web Services",
    "google": "Google",
    "alphabet": "Google",
    "meta": "Meta",
    "facebook": "Meta",
    "microsoft": "Microsoft",
    "msft": "Microsoft",
}

# Technology aliases — concrete tools/libs/frameworks/databases that are not always
# in the skill ontology but must still collapse to one canonical node.
TECH_ALIASES: dict[str, str] = {
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "psql": "PostgreSQL",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "js": "JavaScript",
    "ts": "TypeScript",
    "k8s": "Kubernetes",
    "tf": "TensorFlow",
    "gcp": "Google Cloud Platform",
    "fastapi": "FastAPI",
    "next": "Next.js",
    "nextjs": "Next.js",
    "py": "Python",
}

# Which EvidenceType produces which node type and the candidate->node edge.
_TYPE_MAP: dict[EvidenceType, tuple[GraphNodeType, GraphEdgeType]] = {
    EvidenceType.SKILL: (GraphNodeType.SKILL, GraphEdgeType.HAS_SKILL),
    EvidenceType.TOOL: (GraphNodeType.TECHNOLOGY, GraphEdgeType.USES),
    EvidenceType.PROJECT: (GraphNodeType.PROJECT, GraphEdgeType.BUILT),
    EvidenceType.REPOSITORY: (GraphNodeType.REPOSITORY, GraphEdgeType.CONTRIBUTED_TO),
    EvidenceType.EXPERIENCE: (GraphNodeType.ORGANIZATION, GraphEdgeType.WORKED_AT),
    EvidenceType.EDUCATION: (GraphNodeType.EDUCATION, GraphEdgeType.STUDIED_AT),
    EvidenceType.CERTIFICATION: (GraphNodeType.CERTIFICATION, GraphEdgeType.HOLDS),
    EvidenceType.ACHIEVEMENT: (GraphNodeType.ACHIEVEMENT, GraphEdgeType.ACHIEVED),
    EvidenceType.PUBLICATION: (GraphNodeType.PUBLICATION, GraphEdgeType.ACHIEVED),
    EvidenceType.CONTRIBUTION: (GraphNodeType.CONTRIBUTION, GraphEdgeType.CONTRIBUTED_TO),
    EvidenceType.ASSESSMENT: (GraphNodeType.SKILL, GraphEdgeType.HAS_SKILL),
    EvidenceType.ACTIVITY: (GraphNodeType.CONTRIBUTION, GraphEdgeType.CONTRIBUTED_TO),
    EvidenceType.DOMAIN: (GraphNodeType.DOMAIN, GraphEdgeType.IN_DOMAIN),
}


@dataclass(frozen=True)
class ResolvedEntity:
    """The canonical identity an entity reference resolves to."""

    node_id: str               # stable canonical id, e.g. 'skill:python'
    label: str                 # human display name, e.g. 'Python'
    node_type: GraphNodeType
    candidate_edge: GraphEdgeType  # candidate -> this node
    canonical_key: str         # normalized key used for dedup grouping
    method: str = "exact"      # how it resolved: exact|alias|ontology|fuzzy|slug
    aliases: tuple[str, ...] = field(default_factory=tuple)


def _norm(token: str) -> str:
    return re.sub(r"[\s\-_]+", " ", token.strip().lower())


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "unknown"


class EntityResolver:
    """Resolves raw entity references into canonical :class:`ResolvedEntity`."""

    def __init__(self, fuzzy_threshold: float = FUZZY_THRESHOLD) -> None:
        self.fuzzy_threshold = fuzzy_threshold

    # --- public API ----------------------------------------------------------

    def resolve(self, raw_ref: str, evidence_type: EvidenceType) -> ResolvedEntity:
        """Resolve ``raw_ref`` given the kind of fact it came from."""
        node_type, edge_type = _TYPE_MAP.get(
            evidence_type, (GraphNodeType.SKILL, GraphEdgeType.HAS_SKILL)
        )
        raw = _strip_prefix(raw_ref)

        if node_type in (GraphNodeType.SKILL, GraphNodeType.TECHNOLOGY):
            return self._resolve_skill_like(raw, node_type, edge_type)
        if node_type == GraphNodeType.ORGANIZATION:
            return self._resolve_org(raw, edge_type)
        return self._resolve_generic(raw, node_type, edge_type)

    def same_entity(self, a: str, b: str, node_type: GraphNodeType) -> bool:
        """True if two raw references resolve to the same canonical node."""
        et = _node_to_evidence_type(node_type)
        return self.resolve(a, et).node_id == self.resolve(b, et).node_id

    def similarity(self, a: str, b: str) -> float:
        """Normalized fuzzy similarity in [0, 1] (difflib ratio)."""
        return SequenceMatcher(None, _norm(a), _norm(b)).ratio()

    # --- resolution strategies -----------------------------------------------

    def _resolve_skill_like(
        self, raw: str, node_type: GraphNodeType, edge_type: GraphEdgeType
    ) -> ResolvedEntity:
        key = _norm(raw)
        # Skills and technologies share ONE id namespace: for a candidate, "uses the
        # technology PostgreSQL" and "has the skill PostgreSQL" are the same entity.
        # This makes the same competency collapse to a single node regardless of
        # whether it arrived typed as SKILL or TECHNOLOGY (node_type still differs).
        prefix = "skill"

        # 1. technology alias table (collapses Postgres/postgres/psql -> PostgreSQL)
        if key in TECH_ALIASES:
            canon = TECH_ALIASES[key]
            return ResolvedEntity(
                f"{prefix}:{_slug(canon)}", canon, node_type, edge_type, _norm(canon), "alias"
            )

        # 2. skill ontology (exact / alias hit)
        hit = normalize_skill_hit(raw, source="graph")
        if hit.skill_id != "SKILL_UNKNOWN":
            return ResolvedEntity(
                f"{prefix}:{_slug(hit.canonical_name)}", hit.canonical_name, node_type,
                edge_type, _norm(hit.canonical_name), "ontology", tuple(hit.aliases),
            )

        # 3. fuzzy match against known canonical names
        fuzzy = self._fuzzy_canonical(key)
        if fuzzy:
            return ResolvedEntity(
                f"{prefix}:{_slug(fuzzy)}", fuzzy, node_type, edge_type, _norm(fuzzy), "fuzzy"
            )

        # 4. fall back to the cleaned raw name as its own canonical entity
        canon = hit.canonical_name
        return ResolvedEntity(
            f"{prefix}:{_slug(canon)}", canon, node_type, edge_type, _norm(canon), "slug"
        )

    def _resolve_org(self, raw: str, edge_type: GraphEdgeType) -> ResolvedEntity:
        key = _norm(raw)
        canon = ORG_ALIASES.get(key)
        method = "alias" if canon else "slug"
        if not canon:
            fuzzy = self._fuzzy_org(key)
            canon, method = (fuzzy, "fuzzy") if fuzzy else (raw.strip().title(), "slug")
        return ResolvedEntity(
            f"org:{_slug(canon)}", canon, GraphNodeType.ORGANIZATION, edge_type, _norm(canon), method
        )

    def _resolve_generic(
        self, raw: str, node_type: GraphNodeType, edge_type: GraphEdgeType
    ) -> ResolvedEntity:
        label = raw.strip() or "Unknown"
        return ResolvedEntity(
            f"{node_type.value}:{_slug(label)}", label, node_type, edge_type, _norm(label), "slug"
        )

    # --- fuzzy helpers -------------------------------------------------------

    def _fuzzy_canonical(self, key: str) -> str | None:
        best, score = _best_match(key, _known_canonical_names())
        if best and score >= self.fuzzy_threshold:
            logger.debug("entity fuzzy %r -> %r (%.2f)", key, best, score)
            return best
        return None

    def _fuzzy_org(self, key: str) -> str | None:
        best, score = _best_match(key, tuple(sorted(set(ORG_ALIASES.values()))))
        return best if best and score >= self.fuzzy_threshold else None


# --- module-level helpers + caches --------------------------------------------

def _strip_prefix(raw_ref: str) -> str:
    """Drop a leading 'skill:'/'tech:'/'org:' so providers may pass either form."""
    if ":" in raw_ref and not raw_ref.startswith("http"):
        head, _, tail = raw_ref.partition(":")
        if head.isalpha() and len(head) <= 12 and tail:
            return tail.replace("-", " ").replace("_", " ")
    return raw_ref


@lru_cache(maxsize=1)
def _known_canonical_names() -> tuple[str, ...]:
    from app.knowledge.loader import load_skills

    names: set[str] = set(TECH_ALIASES.values())
    for item in load_skills():
        names.add(item["canonical"])
    return tuple(sorted(names))


def _best_match(key: str, candidates: tuple[str, ...]) -> tuple[str | None, float]:
    best: str | None = None
    best_score = 0.0
    for cand in candidates:
        score = SequenceMatcher(None, key, _norm(cand)).ratio()
        if score > best_score:
            best, best_score = cand, score
    return best, best_score


def _node_to_evidence_type(node_type: GraphNodeType) -> EvidenceType:
    for et, (nt, _edge) in _TYPE_MAP.items():
        if nt == node_type:
            return et
    return EvidenceType.SKILL


# --- legacy functional API (kept for back-compat; prefer EntityResolver) ------

_DEFAULT = EntityResolver()


def resolve_skill(raw: str) -> tuple[str, str]:
    """Back-compat shim. Returns ``(node_id, canonical_name)`` for a skill."""
    hit = normalize_skill_hit(raw, source="graph")
    if hit.skill_id == "SKILL_UNKNOWN":
        canonical = hit.canonical_name
        return f"SKILL_UNKNOWN::{canonical.lower().replace(' ', '_')}", canonical
    return hit.skill_id, hit.canonical_name


def resolve_organization(raw: str) -> tuple[str, str]:
    """Back-compat shim. Returns ``(org_id, canonical_name)`` for an organization."""
    key = raw.strip().lower()
    canonical = ORG_ALIASES.get(key, raw.strip().title())
    org_id = f"ORG::{canonical.lower().replace(' ', '_')}"
    return org_id, canonical
