"""Tests for the Candidate Graph Intelligence Layer.

Covers each engine in isolation and the end-to-end GraphBuilder pipeline, plus the
v2 graph query API. No DB or network required — everything runs in-process.
"""

from __future__ import annotations

import pytest

from app.intelligence.candidate_graph import (
    ConfidenceFusionEngine,
    DuplicateDetector,
    EntityResolver,
    EvidenceLedger,
    GraphBuilder,
    NetworkXGraphStore,
    RelationshipInferenceEngine,
    fuse_confidence,
    graph_registry,
)
from app.intelligence.candidate_graph.ledger import DuplicateEvidenceError
from app.shared.enums import (
    EvidenceSource,
    EvidenceType,
    GraphEdgeType,
    GraphNodeType,
    VerificationStatus,
)
from app.shared.models.evidence import Evidence


def _ev(eid, source, etype, entity_ref, claim, conf, provenance=None):
    return Evidence(
        evidence_id=eid,
        candidate_id="c1",
        source=source,
        evidence_type=etype,
        entity_ref=entity_ref,
        claim=claim,
        confidence=conf,
        provenance=provenance or {},
    )


@pytest.fixture
def python_evidence():
    """Python attested by three sources at different confidences."""
    return [
        _ev("e1", EvidenceSource.RESUME, EvidenceType.SKILL, "Python", "Resume lists Python", 0.6),
        _ev("e2", EvidenceSource.GITHUB, EvidenceType.SKILL, "python", "GitHub: 12k LOC Python", 0.9),
        _ev("e3", EvidenceSource.LINKEDIN, EvidenceType.SKILL, "Python", "LinkedIn skill", 0.7),
    ]


# --------------------------------------------------------------------------- #
# 1. Evidence Ledger
# --------------------------------------------------------------------------- #
class TestEvidenceLedger:
    def test_add_and_query_by_candidate(self, python_evidence):
        ledger = EvidenceLedger()
        ledger.add_all(python_evidence)
        assert len(ledger) == 3
        assert len(ledger.by_candidate("c1")) == 3

    def test_immutable_entries(self, python_evidence):
        ledger = EvidenceLedger()
        ledger.add(python_evidence[0])
        got = ledger.get("e1")
        got.confidence = 0.0  # mutate the returned copy
        assert ledger.get("e1").confidence == 0.6  # store unaffected

    def test_duplicate_id_rejected(self, python_evidence):
        ledger = EvidenceLedger()
        ledger.add(python_evidence[0])
        with pytest.raises(DuplicateEvidenceError):
            ledger.add(python_evidence[0])

    def test_add_all_skips_duplicates(self, python_evidence):
        ledger = EvidenceLedger()
        ledger.add_all(python_evidence)
        added = ledger.add_all(python_evidence)  # all dupes
        assert added == 0

    def test_query_by_entity_and_source(self, python_evidence):
        ledger = EvidenceLedger()
        ledger.add_all(python_evidence)
        assert len(ledger.by_entity("Python")) == 2  # e1, e3 share entity_ref 'Python'
        assert len(ledger.by_source(EvidenceSource.GITHUB)) == 1
        assert ledger.sources_for("Python") == {EvidenceSource.RESUME, EvidenceSource.LINKEDIN}


# --------------------------------------------------------------------------- #
# 2. NetworkX Graph Store
# --------------------------------------------------------------------------- #
class TestGraphStore:
    def test_dynamic_nodes_and_edges(self):
        s = NetworkXGraphStore("g", "c1")
        s.add_node("candidate:c1", GraphNodeType.CANDIDATE, "c1")
        s.add_node("skill:python", GraphNodeType.SKILL, "Python", evidence_ids=["e1"])
        s.add_edge("candidate:c1", "skill:python", GraphEdgeType.HAS_SKILL, evidence_ids=["e1"])
        assert s.has_node("skill:python")
        assert s.neighbors("candidate:c1", GraphEdgeType.HAS_SKILL) == ["skill:python"]

    def test_node_merge_unions_evidence(self):
        s = NetworkXGraphStore("g", "c1")
        s.add_node("skill:python", GraphNodeType.SKILL, "Python", evidence_ids=["e1"])
        s.add_node("skill:py", GraphNodeType.SKILL, "Py", evidence_ids=["e2"])
        s.merge_nodes("skill:python", "skill:py")
        assert not s.has_node("skill:py")
        assert set(s.get_node("skill:python")["evidence_ids"]) == {"e1", "e2"}

    def test_traversal(self):
        s = NetworkXGraphStore("g", "c1")
        s.add_node("a", GraphNodeType.CANDIDATE, "a")
        s.add_node("b", GraphNodeType.REPOSITORY, "b")
        s.add_node("c", GraphNodeType.TECHNOLOGY, "c")
        s.add_edge("a", "b", GraphEdgeType.BUILT)
        s.add_edge("b", "c", GraphEdgeType.USES)
        assert set(s.traverse("a", max_depth=2)) == {"b", "c"}
        assert s.traverse("a", max_depth=1) == ["b"]

    def test_export_import_roundtrip(self):
        s = NetworkXGraphStore("g", "c1", "j1")
        s.add_node("skill:python", GraphNodeType.SKILL, "Python", evidence_ids=["e1"])
        payload = s.to_dict()
        restored = NetworkXGraphStore.from_dict(payload)
        assert restored.graph_id == "g"
        assert restored.has_node("skill:python")


# --------------------------------------------------------------------------- #
# 3. Entity Resolution
# --------------------------------------------------------------------------- #
class TestEntityResolver:
    def test_alias_normalization(self):
        r = EntityResolver()
        assert r.resolve("JS", EvidenceType.SKILL).node_id == r.resolve("JavaScript", EvidenceType.SKILL).node_id
        assert r.resolve("Postgres", EvidenceType.TOOL).label == "PostgreSQL"
        assert r.resolve("Node", EvidenceType.TOOL).label == "Node.js"

    def test_org_aliases(self):
        r = EntityResolver()
        assert r.resolve("aws", EvidenceType.EXPERIENCE).node_id == r.resolve(
            "Amazon Web Services", EvidenceType.EXPERIENCE
        ).node_id

    def test_prefix_stripping(self):
        r = EntityResolver()
        a = r.resolve("skill:python", EvidenceType.SKILL)
        b = r.resolve("Python", EvidenceType.SKILL)
        assert a.node_id == b.node_id

    def test_same_entity_and_similarity(self):
        r = EntityResolver()
        assert r.same_entity("k8s", "Kubernetes", GraphNodeType.SKILL)
        assert r.similarity("PostgreSQL", "Postgres DB") > 0.6


# --------------------------------------------------------------------------- #
# 4. Confidence Fusion
# --------------------------------------------------------------------------- #
class TestConfidenceFusion:
    def test_multi_source_fusion_is_high(self):
        # resume 0.6, github 0.9, linkedin 0.7 -> strong corroboration
        score = fuse_confidence([("resume", 0.6), ("github", 0.9), ("linkedin", 0.7)])
        assert score > 0.9

    def test_github_outweighs_resume(self):
        gh = fuse_confidence([("github", 0.8)])
        rs = fuse_confidence([("resume", 0.8)])
        assert gh > rs

    def test_detailed_status_corroborated(self):
        eng = ConfidenceFusionEngine()
        res = eng.fuse_detailed([("resume", 0.6), ("github", 0.9)])
        assert res.source_count == 2
        assert res.verification_status == VerificationStatus.CORROBORATED
        assert 0.0 < res.claim_strength <= 1.0

    def test_manual_is_verified(self):
        eng = ConfidenceFusionEngine()
        res = eng.fuse_detailed([("manual", 0.9)])
        assert res.verification_status == VerificationStatus.VERIFIED

    def test_empty_is_zero(self):
        assert fuse_confidence([]) == 0.0


# --------------------------------------------------------------------------- #
# 5. Duplicate Detection
# --------------------------------------------------------------------------- #
class TestDuplicateDetection:
    def test_collapse_fuzzy_labels(self):
        s = NetworkXGraphStore("g", "c1")
        s.add_node("repo:clinicbot", GraphNodeType.REPOSITORY, "ClinicBot", evidence_ids=["e1"])
        s.add_node("repo:clinic-bot", GraphNodeType.REPOSITORY, "Clinic Bot", evidence_ids=["e2"])
        merged = DuplicateDetector(threshold=0.8).collapse(s)
        assert len(merged) == 1
        # evidence from both survives on the kept node
        kept = merged[0].keep_id
        assert set(s.get_node(kept)["evidence_ids"]) == {"e1", "e2"}


# --------------------------------------------------------------------------- #
# 6. Relationship Inference
# --------------------------------------------------------------------------- #
class TestRelationshipInference:
    def test_repo_tech_and_capability_inference(self):
        s = NetworkXGraphStore("g", "c1")
        s.add_node("candidate:c1", GraphNodeType.CANDIDATE, "c1")
        s.add_node(
            "repo:clinicbot", GraphNodeType.REPOSITORY, "ClinicBot",
            confidence=0.9, evidence_ids=["e1"],
            attributes={"technologies": ["FastAPI", "Python"]},
        )
        s.add_edge("candidate:c1", "repo:clinicbot", GraphEdgeType.CONTRIBUTED_TO)
        RelationshipInferenceEngine().expand(s, "candidate:c1")

        # repo USES a technology (skills+technologies share the 'skill:' namespace,
        # so identify a technology by node *type*, not id prefix)
        uses = s.neighbors("repo:clinicbot", GraphEdgeType.USES)
        assert uses and any(s.get_node(t)["type"] == GraphNodeType.TECHNOLOGY for t in uses)
        # FastAPI implies a Backend Development capability domain on the candidate
        domains = s.neighbors("candidate:c1", GraphEdgeType.IN_DOMAIN)
        labels = {s.get_node(d)["label"] for d in domains}
        assert "Backend Development" in labels


# --------------------------------------------------------------------------- #
# 7. End-to-end GraphBuilder
# --------------------------------------------------------------------------- #
class TestGraphBuilder:
    def test_full_pipeline(self, python_evidence):
        extra = [
            _ev("e4", EvidenceSource.GITHUB, EvidenceType.REPOSITORY, "ClinicBot",
                "Built ClinicBot", 0.9, {"technologies": ["FastAPI"]}),
            _ev("e5", EvidenceSource.MANUAL, EvidenceType.CERTIFICATION, "AWS Certified",
                "AWS cert", 0.95),
        ]
        graph = GraphBuilder().build("c1", python_evidence + extra, job_id="j1")

        assert graph.graph_id == "graph:c1:j1"
        # Python collapsed to a single node despite 3 evidence entries
        py = next(n for n in graph.nodes if n.id == "skill:python")
        assert py.confidence > 0.9
        assert len(py.evidence_ids) == 3
        assert py.attributes["verification_status"] == VerificationStatus.CORROBORATED.value
        # ledger entries bound to nodes
        assert len(graph.evidence_ledger) == 5
        assert all(e.supporting_node_id for e in graph.evidence_ledger)
        # inference produced a backend capability beyond explicit claims
        assert any(n.attributes.get("inferred") for n in graph.nodes)

    def test_evidence_for_node(self, python_evidence):
        graph = GraphBuilder().build("c1", python_evidence)
        ev = graph.evidence_for("skill:python")
        assert len(ev) == 3


# --------------------------------------------------------------------------- #
# 8. Graph Query API
# --------------------------------------------------------------------------- #
class TestGraphAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from app.main import app

        return TestClient(app)

    @pytest.fixture
    def built(self, client):
        payload = {
            "candidate_id": "apicand",
            "evidence": [
                _ev("a1", EvidenceSource.GITHUB, EvidenceType.SKILL, "Python", "py", 0.9).model_dump(mode="json"),
                _ev("a2", EvidenceSource.GITHUB, EvidenceType.REPOSITORY, "ClinicBot", "repo", 0.9,
                    {"technologies": ["FastAPI"]}).model_dump(mode="json"),
            ],
        }
        resp = client.post("/v2/graph/build", json=payload)
        assert resp.status_code == 200
        return resp.json()

    def test_build_and_fetch(self, client, built):
        gid = built["graph_id"]
        assert client.get(f"/v2/graph/{gid}").status_code == 200
        assert client.get(f"/v2/graph/{gid}/skills").json()
        summary = client.get(f"/v2/graph/{gid}/summary").json()
        assert summary["node_count"] > 0

    def test_confidence_and_evidence(self, client, built):
        gid = built["graph_id"]
        conf = client.get(f"/v2/graph/{gid}/confidence/skill:python").json()
        assert conf["node_id"] == "skill:python"
        assert conf["confidence"] > 0
        ev = client.get(f"/v2/graph/{gid}/evidence", params={"node_id": "skill:python"}).json()
        assert len(ev) == 1

    def test_query_and_relationships(self, client, built):
        gid = built["graph_id"]
        hits = client.get(f"/v2/graph/{gid}/query", params={"q": "python"}).json()
        assert any(h["id"] == "skill:python" for h in hits)
        rels = client.get(f"/v2/graph/{gid}/relationships").json()
        assert len(rels) > 0

    def test_missing_graph_404(self, client):
        assert client.get("/v2/graph/nope").status_code == 404
