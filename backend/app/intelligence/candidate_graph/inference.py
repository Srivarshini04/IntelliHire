"""Relationship Inference Engine — derive hidden edges from existing evidence.

Providers emit only *observed* facts (DECISION C). The inference engine reads the
assembled graph and grows it with relationships nobody stated explicitly but that
the evidence implies. Every inferred edge is:

  * **discounted** — inference is weaker than observation, so confidence is the
    supporting nodes' confidence times an ``inference_discount``;
  * **traceable** — it carries the union of the supporting nodes' ``evidence_ids``
    and ``attributes['inferred'] = True`` + a ``rule`` tag, so explainability can
    always show *why* an edge exists.

Rules implemented
-----------------
  1. repo/project ``USES`` technology         (from node provenance: languages/topics)
  2. repo/project ``PROVES`` skill + inferred candidate ``HAS_SKILL``
  3. technology/skill co-occurrence ``RELATED_TO``  (shared repo/project)
  4. certification ``VALIDATES`` skill
  5. technology -> ``DOMAIN`` capability ``IN_DOMAIN``  (e.g. FastAPI+Python => backend)
  6. organization -> ``DOMAIN`` (company-domain mapping)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.intelligence.candidate_graph.entity_resolver import EntityResolver, _slug
from app.intelligence.candidate_graph.graph_store import NetworkXGraphStore
from app.shared.enums import EvidenceType, GraphEdgeType, GraphNodeType

logger = logging.getLogger(__name__)

# Technology -> capability domain. The signature inference: a repo using FastAPI
# plus Python implies *backend development* capability beyond the explicit claim.
TECH_DOMAINS: dict[str, str] = {
    "fastapi": "Backend Development",
    "django": "Backend Development",
    "flask": "Backend Development",
    "express": "Backend Development",
    "node.js": "Backend Development",
    "spring": "Backend Development",
    "react": "Frontend Development",
    "vue": "Frontend Development",
    "angular": "Frontend Development",
    "next.js": "Frontend Development",
    "tensorflow": "Machine Learning",
    "pytorch": "Machine Learning",
    "scikit-learn": "Machine Learning",
    "keras": "Machine Learning",
    "docker": "DevOps",
    "kubernetes": "DevOps",
    "terraform": "DevOps",
    "ansible": "DevOps",
    "postgresql": "Data Engineering",
    "mongodb": "Data Engineering",
    "kafka": "Data Engineering",
    "spark": "Data Engineering",
}

# Organization -> primary domain (company-domain mapping; extend freely).
ORG_DOMAINS: dict[str, str] = {
    "amazon web services": "Cloud Infrastructure",
    "google": "Search & AI",
    "meta": "Social & AdTech",
    "microsoft": "Enterprise Software",
}

# Keys in node attributes that may list technologies for a repo/project.
_TECH_ATTR_KEYS = ("technologies", "languages", "topics", "stack", "frameworks", "tools")


@dataclass(frozen=True)
class InferredEdge:
    source_id: str
    target_id: str
    edge_type: GraphEdgeType
    rule: str
    confidence: float


class RelationshipInferenceEngine:
    """Expand a graph with inferred relationships derived from its own evidence."""

    def __init__(
        self, resolver: EntityResolver | None = None, inference_discount: float = 0.7
    ) -> None:
        self.resolver = resolver or EntityResolver()
        self.discount = inference_discount

    def expand(self, store: NetworkXGraphStore, candidate_node_id: str) -> list[InferredEdge]:
        """Run every rule. Returns the inferred edges (also written into ``store``)."""
        inferred: list[InferredEdge] = []
        inferred += self._infer_repo_technologies(store, candidate_node_id)
        inferred += self._infer_cooccurrence(store)
        inferred += self._infer_cert_validations(store)
        inferred += self._infer_domains(store, candidate_node_id)
        inferred += self._infer_org_domains(store, candidate_node_id)
        if inferred:
            logger.info("inference added %d edge(s)", len(inferred))
        store.metadata["inferred_edge_count"] = len(inferred)
        return inferred

    # --- rule 1+2: repo/project -> technology (USES) + skill (PROVES) ---------

    def _infer_repo_technologies(
        self, store: NetworkXGraphStore, candidate_node_id: str
    ) -> list[InferredEdge]:
        out: list[InferredEdge] = []
        artefact_types = (GraphNodeType.REPOSITORY, GraphNodeType.PROJECT)
        for node_type in artefact_types:
            for artefact in store.nodes_of_type(node_type):
                data = store.get_node(artefact) or {}
                techs = _collect_techs(data.get("attributes", {}))
                base_conf = float(data.get("confidence", 0.6))
                ev_ids = data.get("evidence_ids", [])
                for raw_tech in techs:
                    # One node per competency (skills+technologies share a namespace),
                    # so a repo's "Python" collapses onto an explicitly-claimed Python.
                    resolved = self.resolver.resolve(raw_tech, EvidenceType.TOOL)
                    conf = round(base_conf * self.discount, 4)
                    store.add_node(
                        resolved.node_id, GraphNodeType.TECHNOLOGY, resolved.label,
                        confidence=conf, evidence_ids=ev_ids,
                        attributes={"inferred": True},
                    )
                    # artefact USES + PROVES the technology; candidate HAS_SKILL it (inferred).
                    self._add(store, out, artefact, resolved.node_id, GraphEdgeType.USES,
                              "repo_uses_tech", conf, ev_ids)
                    self._add(store, out, artefact, resolved.node_id, GraphEdgeType.PROVES,
                              "repo_proves_skill", conf, ev_ids)
                    self._add(store, out, candidate_node_id, resolved.node_id,
                              GraphEdgeType.HAS_SKILL, "inferred_skill", conf, ev_ids)
        return out

    # --- rule 3: technology/skill co-occurrence (RELATED_TO) -----------------

    def _infer_cooccurrence(self, store: NetworkXGraphStore) -> list[InferredEdge]:
        out: list[InferredEdge] = []
        artefacts = store.nodes_of_type(GraphNodeType.REPOSITORY) + store.nodes_of_type(
            GraphNodeType.PROJECT
        )
        for artefact in artefacts:
            used = [
                t for t in store.neighbors(artefact, GraphEdgeType.USES)
            ] + [s for s in store.neighbors(artefact, GraphEdgeType.PROVES)]
            used = list(dict.fromkeys(used))  # dedupe, keep order
            for i in range(len(used)):
                for j in range(i + 1, len(used)):
                    a, b = used[i], used[j]
                    conf = round(
                        min(_conf(store, a), _conf(store, b)) * self.discount, 4
                    )
                    self._add(store, out, a, b, GraphEdgeType.RELATED_TO,
                              "cooccurrence", conf, [])
        return out

    # --- rule 4: certification -> skill (VALIDATES) --------------------------

    def _infer_cert_validations(self, store: NetworkXGraphStore) -> list[InferredEdge]:
        out: list[InferredEdge] = []
        skills = {
            (store.get_node(s) or {}).get("label", "").lower(): s
            for s in store.nodes_of_type(GraphNodeType.SKILL)
        }
        for cert in store.nodes_of_type(GraphNodeType.CERTIFICATION):
            data = store.get_node(cert) or {}
            text = f"{data.get('label', '')} {data.get('attributes', {}).get('subject', '')}".lower()
            ev_ids = data.get("evidence_ids", [])
            conf = round(float(data.get("confidence", 0.8)) * self.discount, 4)
            for label, skill_id in skills.items():
                if label and label in text:
                    self._add(store, out, cert, skill_id, GraphEdgeType.VALIDATES,
                              "cert_validates_skill", conf, ev_ids)
        return out

    # --- rule 5: technology -> capability domain (IN_DOMAIN) -----------------

    def _infer_domains(
        self, store: NetworkXGraphStore, candidate_node_id: str
    ) -> list[InferredEdge]:
        out: list[InferredEdge] = []
        for tech in store.nodes_of_type(GraphNodeType.TECHNOLOGY):
            label = (store.get_node(tech) or {}).get("label", "").lower()
            domain_name = TECH_DOMAINS.get(label)
            if not domain_name:
                continue
            domain_id = f"domain:{_slug(domain_name)}"
            conf = round(_conf(store, tech) * self.discount, 4)
            store.add_node(domain_id, GraphNodeType.DOMAIN, domain_name,
                           confidence=conf, attributes={"inferred": True})
            self._add(store, out, tech, domain_id, GraphEdgeType.IN_DOMAIN,
                      "tech_in_domain", conf, [])
            self._add(store, out, candidate_node_id, domain_id, GraphEdgeType.IN_DOMAIN,
                      "inferred_capability", conf, [])
        return out

    # --- rule 6: organization -> domain (company-domain mapping) -------------

    def _infer_org_domains(
        self, store: NetworkXGraphStore, candidate_node_id: str
    ) -> list[InferredEdge]:
        out: list[InferredEdge] = []
        for org in store.nodes_of_type(GraphNodeType.ORGANIZATION):
            label = (store.get_node(org) or {}).get("label", "").lower()
            domain_name = ORG_DOMAINS.get(label)
            if not domain_name:
                continue
            domain_id = f"domain:{_slug(domain_name)}"
            conf = round(_conf(store, org) * self.discount, 4)
            store.add_node(domain_id, GraphNodeType.DOMAIN, domain_name,
                           confidence=conf, attributes={"inferred": True})
            self._add(store, out, org, domain_id, GraphEdgeType.IN_DOMAIN,
                      "company_in_domain", conf, [])
        return out

    # --- helpers -------------------------------------------------------------

    def _add(
        self, store: NetworkXGraphStore, out: list[InferredEdge],
        src: str, tgt: str, edge_type: GraphEdgeType, rule: str,
        confidence: float, evidence_ids: list[str],
    ) -> None:
        if src == tgt:
            return
        store.add_edge(
            src, tgt, edge_type, confidence=confidence, evidence_ids=evidence_ids,
            attributes={"inferred": True, "rule": rule},
        )
        out.append(InferredEdge(src, tgt, edge_type, rule, confidence))


def _conf(store: NetworkXGraphStore, node_id: str) -> float:
    return float((store.get_node(node_id) or {}).get("confidence", 0.5))


def _collect_techs(attributes: dict) -> list[str]:
    """Pull a flat, de-duplicated list of technology names from node attributes."""
    techs: list[str] = []
    for key in _TECH_ATTR_KEYS:
        val = attributes.get(key)
        if isinstance(val, str):
            techs.append(val)
        elif isinstance(val, (list, tuple)):
            techs.extend(str(v) for v in val)
        elif isinstance(val, dict):  # e.g. {"Python": 12000, "HTML": 400}
            techs.extend(str(k) for k in val)
    return list(dict.fromkeys(t for t in techs if t.strip()))
