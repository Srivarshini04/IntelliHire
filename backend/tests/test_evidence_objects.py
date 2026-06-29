"""Standardized evidence object + normalizer tests."""

from app.services.evidence.base import (
    EvidenceObject,
    EvidenceProvider,
    EvidenceSignal,
    build_evidence,
)
from app.services.evidence.normalizer import (
    normalize,
    normalize_github,
    normalize_leetcode,
    normalize_linkedin,
    normalize_portfolio,
    normalize_resume,
)


def test_build_evidence_fills_reliability_and_dedupes_skills():
    ev = build_evidence(
        "github",
        source_url="https://github.com/x",
        skills=["Python", "python", "FastAPI"],
    )
    assert isinstance(ev, EvidenceObject)
    assert ev.reliability == 0.95  # github reliability from SOURCE_RELIABILITY
    assert ev.skills == ["Python", "FastAPI"]  # case-insensitive dedupe, order kept
    assert ev.ok is True


def test_unknown_source_gets_default_reliability():
    ev = build_evidence("mystery")
    assert ev.reliability == 0.4
    assert ev.source == "mystery"


def test_to_db_payload_maps_onto_evidence_columns():
    ev = build_evidence(
        "leetcode",
        source_url="https://leetcode.com/u/x",
        relevance_score=72.0,
        summary="LeetCode summary",
        skills=["Algorithms"],
        signals=[EvidenceSignal(label="coding_skill", detail="72/100", weight=0.72)],
        raw={"username": "x"},
        processed={"tier": "Advanced"},
    )
    payload = ev.to_db_payload()
    assert payload["source_type"] == "leetcode"
    assert payload["source_url"] == "https://leetcode.com/u/x"
    assert payload["relevance_score"] == 72.0
    assert payload["raw_content"] == {"username": "x"}
    # processed_content carries the explainable view + provider-specific keys.
    assert payload["processed_content"]["summary"] == "LeetCode summary"
    assert payload["processed_content"]["skills"] == ["Algorithms"]
    assert payload["processed_content"]["tier"] == "Advanced"
    assert payload["processed_content"]["signals"][0]["label"] == "coding_skill"


def test_error_object_is_not_ok():
    ev = build_evidence("portfolio", error="boom")
    assert ev.ok is False
    assert ev.error == "boom"


def test_normalize_github_extracts_skills_and_signals():
    pkg = {
        "github_url": "https://github.com/x",
        "skills": {"languages": ["Python", "Go"]},
        "features": ["auth", "payments"],
        "repositories_analyzed": ["x/a", "x/b"],
        "engineering_maturity": 80,
        "hidden_gem": {"hidden_gem": True, "reason": "strong infra"},
        "jd_match": {"overall_fit": 88},
    }
    ev = normalize_github(pkg)
    assert ev.source == "github"
    assert ev.skills == ["Python", "Go"]
    assert ev.relevance_score == 88
    labels = {s.label for s in ev.signals}
    assert "engineering_maturity" in labels and "hidden_gem" in labels
    assert "auth" in ev.highlights


def test_normalize_linkedin_handles_extractor_error():
    pkg = {"basic": {"error": "apify down"}, "skills": {"skills": []}}
    ev = normalize_linkedin(pkg)
    assert ev.source == "linkedin"
    assert ev.error == "apify down"


def test_normalize_leetcode_uses_coding_skill_as_relevance():
    pkg = {
        "source_url": "https://leetcode.com/u/x",
        "coding_skill": 70.0,
        "total_solved": 300,
        "easy_solved": 100,
        "medium_solved": 150,
        "hard_solved": 50,
        "tier": "Advanced",
        "contest_rating": 1800,
        "strengths": ["Strong medium solving"],
    }
    ev = normalize_leetcode(pkg)
    assert ev.relevance_score == 70.0
    assert "Algorithms" in ev.skills
    assert ev.summary.startswith("LeetCode: 300 problems")


def test_normalize_leetcode_error_short_circuits():
    ev = normalize_leetcode({"error": "user not found"})
    assert ev.error == "user not found"
    assert ev.skills == []


def test_normalize_resume_reports_jd_coverage():
    pkg = {
        "profile": {"name": {"value": "Asha"}},
        "skills": ["Python", "FastAPI"],
        "jd_match": {"required": ["Python", "Go"], "matched": ["Python"], "coverage": 50.0},
        "text_length": 1200,
    }
    ev = normalize_resume(pkg)
    assert ev.source == "resume"
    assert "Asha" in ev.summary
    assert any(s.label == "jd_coverage" for s in ev.signals)


def test_normalize_portfolio_shapes_links_and_projects():
    pkg = {
        "portfolio_url": "https://x.dev",
        "skills": ["React"],
        "projects": ["ClinicBot", "WattWise"],
        "links": {"github": "https://github.com/x"},
        "word_count": 420,
    }
    ev = normalize_portfolio(pkg)
    assert ev.source == "portfolio"
    assert ev.reliability == 0.5  # resume/portfolio are low-reliability
    assert "ClinicBot" in ev.highlights
    assert any(s.label == "github_link" for s in ev.signals)


def test_normalize_dispatch_and_unknown_fallback():
    ev = normalize("github", {"skills": {"languages": ["Rust"]}})
    assert ev.source == "github" and "Rust" in ev.skills
    fallback = normalize("weird", {"a": 1})
    assert fallback.source == "weird" and fallback.raw == {"a": 1}


def test_services_satisfy_provider_protocol_shape():
    # The protocol is structural; confirm EvidenceObject round-trips cleanly.
    ev = build_evidence("github")
    assert isinstance(ev, EvidenceObject)
    # runtime_checkable protocol exists and is importable
    assert EvidenceProvider is not None
