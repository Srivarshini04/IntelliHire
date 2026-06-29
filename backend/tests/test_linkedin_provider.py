"""LinkedIn evidence provider tests (no network / no LLM)."""

import asyncio

from app.services.evidence import linkedin_service
from app.services.evidence.linkedin_service import analyze_linkedin_evidence


class _FakeExtraction:
    def to_dict(self):
        return {
            "features": ["recommendation_engine"],
            "feature_evidence": {},
            "skill_claims": ["Python", "MLOps"],
            "scale": {"users": 50000},
            "ownership": "Team Lead",
            "production": True,
            "experiences": [{"organization": "Acme", "snippet": "Led ML platform"}],
            "extraction_source": "fake",
        }


def test_analyze_linkedin_evidence_merges_basic_and_deep(monkeypatch):
    monkeypatch.setattr(
        linkedin_service,
        "_fetch_raw",
        lambda url: {
            "profile": {"name": "Venu"},
            "experiences": [{"organization": "Acme"}],
            "education": [{"school": "IIT"}],
            "skills": ["Python", "Docker"],
            "certifications": ["AWS SA"],
            "profile_text": "Led ML platform at Acme. Python, Docker, MLOps.",
        },
    )
    monkeypatch.setattr(
        linkedin_service,
        "extract_linkedin",
        lambda text, skills, caps: (_FakeExtraction(), "fake"),
    )

    result = asyncio.run(
        analyze_linkedin_evidence(
            "https://www.linkedin.com/in/venu",
            role_blueprint={"skills": ["Python"], "capabilities": ["ml_engineering"]},
        )
    )
    assert result["source"] == "linkedin"
    assert result["ownership"] == "Team Lead"
    assert result["production"] is True
    # declared skills + LLM skill claims merge & de-dup.
    merged = result["skills"]["skills"]
    assert "Python" in merged and "Docker" in merged and "MLOps" in merged
    assert "recommendation_engine" in result["features"]
    assert result["education"] == [{"school": "IIT"}]


def test_analyze_linkedin_evidence_handles_empty_profile_text(monkeypatch):
    # No profile text → deep analysis returns empty without invoking the LLM.
    monkeypatch.setattr(
        linkedin_service,
        "_fetch_raw",
        lambda url: {
            "profile": {},
            "experiences": [],
            "education": [],
            "skills": [],
            "certifications": [],
            "profile_text": "",
        },
    )
    called = {"llm": False}

    def _should_not_run(*a, **k):
        called["llm"] = True
        raise AssertionError("extract_linkedin must not run without profile text")

    monkeypatch.setattr(linkedin_service, "extract_linkedin", _should_not_run)

    result = asyncio.run(analyze_linkedin_evidence("https://www.linkedin.com/in/ghost"))
    assert result["source"] == "linkedin"
    assert result["ownership"] == "Unknown"
    assert result["features"] == []
    assert called["llm"] is False
