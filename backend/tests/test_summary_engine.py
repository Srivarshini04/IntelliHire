"""Candidate brief-summary engine tests."""

from app.services.summary.summary_engine import build_candidate_summary

_EVIDENCE = {
    "github": {
        "skills": {"languages": ["Python", "Go"], "topics": ["ml"]},
        "features": ["auth", "payments", "search"],
        "capabilities": {"backend_engineering": 80, "ml_engineering": 40},
        "engineering_maturity": 78,
        "maintenance_score": 0.7,
        "repositories_analyzed": ["x/a", "x/b", "x/c"],
        "hidden_gem": {"hidden_gem": True, "reason": "production infra rarely seen at this level"},
    },
    "leetcode": {
        "total_solved": 300,
        "easy_solved": 100,
        "medium_solved": 150,
        "hard_solved": 50,
        "coding_skill": 74,
        "tier": "Advanced",
        "ranking": 50000,
        "contest_rating": 1800,
        "acceptance_rate": 62,
        "strengths": ["Strong medium-level problem solving"],
        "improvements": ["Solve more hard problems"],
    },
    "linkedin": {
        "experiences": [{"organization": "Acme"}, {"organization": "Beta"}, {"organization": "Gamma"}],
        "ownership": "Team Lead",
        "production": True,
        "scale": {"users": 50000},
        "skills": {"skills": ["Python", "Kubernetes"], "certifications": ["AWS SA"]},
        "features": ["ml platform"],
    },
    "resume": {
        "skills": ["Python", "FastAPI", "Docker"],
        "jd_match": {"required": ["Python", "Go", "Rust"], "matched": ["Python"], "coverage": 33.0},
        "text_length": 2200,
    },
}


def test_summary_covers_every_present_source():
    summary = build_candidate_summary(
        "Asha",
        _EVIDENCE,
        capability={"capability_score": 72},
        risk={"role_gap_risk": 20, "credibility_risk": 30, "evidence_risk": 10, "risk_score": 25},
        hti={"hti_score": 60},
        required_skills=["Python", "Go", "Rust"],
    )
    sources = {s.source for s in summary.sources}
    assert sources == {"github", "leetcode", "linkedin", "resume"}
    # Source order is strongest-evidence first.
    assert summary.sources[0].source == "github"


def test_leetcode_section_surfaces_concrete_stats():
    summary = build_candidate_summary("Asha", _EVIDENCE)
    lc = next(s for s in summary.sources if s.source == "leetcode")
    labels = {st.label: st.value for st in lc.stats}
    assert labels["Total solved"] == "300"
    assert labels["Easy / Medium / Hard"] == "100 / 150 / 50"
    assert labels["Coding skill"] == "74/100"
    assert any("Coding skill 74/100" in s for s in lc.strengths)


def test_github_strengths_and_hidden_gem():
    summary = build_candidate_summary("Asha", _EVIDENCE)
    gh = next(s for s in summary.sources if s.source == "github")
    assert any("engineering maturity" in s.lower() for s in gh.strengths)
    assert any("Hidden gem" in s for s in gh.strengths)


def test_role_fit_strong_when_gap_low():
    summary = build_candidate_summary(
        "Asha",
        _EVIDENCE,
        risk={"role_gap_risk": 20},
        required_skills=["Python", "Go", "Rust"],
    )
    assert summary.role_fit.verdict == "Strong match"
    assert summary.role_fit.fit_score == 80.0
    assert "Python" in summary.role_fit.matched_skills
    # Go is in github languages → matched; Rust nowhere → missing.
    assert "Rust" in summary.role_fit.missing_skills


def test_role_fit_weak_when_gap_high():
    summary = build_candidate_summary(
        "Asha",
        {"resume": _EVIDENCE["resume"]},
        risk={"role_gap_risk": 89},
        required_skills=["Python", "Go", "Rust"],
    )
    assert summary.role_fit.verdict == "Weak match"
    assert summary.role_fit.fit_score == 11.0


def test_overall_lists_are_tagged_by_source_and_capped():
    summary = build_candidate_summary(
        "Asha",
        _EVIDENCE,
        capability={"capability_score": 72},
        risk={"credibility_risk": 80, "evidence_risk": 10},
    )
    assert summary.overall_strengths
    assert any(s.startswith("[GitHub]") or s.startswith("[LeetCode]") for s in summary.overall_strengths)
    assert any("Credibility risk high" in w for w in summary.overall_weaknesses)
    assert len(summary.overall_strengths) <= 8


def test_errored_source_shown_as_unavailable():
    summary = build_candidate_summary(
        "Asha",
        {"github": _EVIDENCE["github"], "portfolio": {"error": "connection refused"}},
    )
    by_source = {s.source: s for s in summary.sources}
    assert set(by_source) == {"github", "portfolio"}
    assert by_source["portfolio"].available is False
    assert "connection refused" in by_source["portfolio"].headline
    # An unavailable source must NOT be counted as a candidate weakness.
    assert not any("Portfolio" in w for w in summary.overall_weaknesses)


def test_linkedin_without_data_is_unavailable_not_weak():
    linkedin_empty = {
        "source": "linkedin",
        "available": False,
        "error": "LinkedIn data unavailable — APIFY_TOKEN not configured",
        "experiences": [],
        "skills": {"skills": []},
        "features": [],
        "ownership": "Unknown",
        "production": False,
    }
    summary = build_candidate_summary("Asha", {"linkedin": linkedin_empty})
    li = next(s for s in summary.sources if s.source == "linkedin")
    assert li.available is False
    assert "APIFY_TOKEN" in li.headline
    assert li.weaknesses == []  # no fabricated weaknesses
    assert not any("LinkedIn" in w for w in summary.overall_weaknesses)


def test_headline_mentions_verdict_and_sources():
    summary = build_candidate_summary(
        "Asha", _EVIDENCE, capability={"capability_score": 72}, hti={"hti_score": 60},
        risk={"role_gap_risk": 20}, required_skills=["Python"],
    )
    assert "Asha" in summary.headline
    assert "match" in summary.headline.lower()
    assert "GitHub" in summary.headline
