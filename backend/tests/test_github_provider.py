"""GitHub evidence provider tests (no network / no DB)."""

import asyncio

from app.services.evidence import github_service
from app.services.evidence.github_service import analyze_github_evidence
from app.services.evidence.relevance_engine import github_artifacts
from app.services.evidence.skill_extractor import extract_skills


def test_extract_skills_ranks_languages_by_bytes_and_collects_topics():
    github_data = {
        "repos": [
            {"languages": {"Python": 9000, "HTML": 1000}, "topics": ["ML", "fastapi"]},
            {"languages": {"Python": 2000, "Go": 5000}, "topics": ["Go"]},
        ]
    }
    skills = extract_skills(github_data)
    # Python (11000) > Go (5000) > HTML (1000)
    assert skills["languages"][0] == "Python"
    assert "Go" in skills["languages"]
    assert skills["topics"] == ["fastapi", "go", "ml"]  # lower-cased + sorted


def test_github_artifacts_built_from_repos():
    pkg = {
        "repos": [
            {"name": "clinicbot", "description": "AI triage", "language": "Python", "topics": ["ml"]},
        ]
    }
    artifacts = github_artifacts(pkg)
    assert len(artifacts) == 1
    assert artifacts[0]["name"] == "clinicbot"
    assert artifacts[0]["source"] == "github"
    assert "Python" in artifacts[0]["text"]


def test_analyze_github_evidence_aggregates_basic_deep_and_leetcode(monkeypatch):
    async def _noop_db():
        return None

    monkeypatch.setattr(github_service, "_ensure_intel_db", _noop_db)
    monkeypatch.setattr(
        github_service,
        "_run_basic_extraction",
        lambda url: {
            "profile": {"login": "venu"},
            "repos": [{"name": "a"}],
            "events": [],
            "skills": {"languages": ["Python"], "topics": ["ml"]},
        },
    )
    monkeypatch.setattr(
        github_service,
        "_run_deep_analysis",
        lambda url, skills, li, rt: {
            "skill_scores": {"FastAPI": 80},
            "candidate_capabilities": {"backend_engineering": 75},
            "candidate_features": ["auth"],
            "engineering_maturity": 70,
            "repositories_analyzed": ["venu/a"],
            "jd_match": {"overall_fit": 82},
            "metadata": {"maintenance_score": 0.6},
        },
    )

    result = asyncio.run(
        analyze_github_evidence("https://github.com/venu", role_blueprint={"skills": ["FastAPI"]})
    )
    assert result["source"] == "github"
    assert result["github_url"] == "https://github.com/venu"
    # languages merge basic + deep skill scores, de-duplicated.
    assert "Python" in result["skills"]["languages"]
    assert "FastAPI" in result["skills"]["languages"]
    assert result["capabilities"] == {"backend_engineering": 75}
    assert result["features"] == ["auth"]
    assert result["leetcode"] is None  # no leetcode_url supplied


def test_analyze_github_evidence_includes_leetcode_when_url_present(monkeypatch):
    async def _noop_db():
        return None

    monkeypatch.setattr(github_service, "_ensure_intel_db", _noop_db)
    monkeypatch.setattr(github_service, "_run_basic_extraction", lambda url: {"skills": {"languages": []}, "repos": [], "events": []})
    monkeypatch.setattr(github_service, "_run_deep_analysis", lambda *a, **k: {})

    async def _fake_lc(url):
        return {"coding_skill": 80, "tier": "Advanced"}

    monkeypatch.setattr(github_service, "_evaluate_leetcode", _fake_lc)

    result = asyncio.run(
        analyze_github_evidence("https://github.com/venu", leetcode_url="https://leetcode.com/u/venu")
    )
    assert result["leetcode"] == {"coding_skill": 80, "tier": "Advanced"}
