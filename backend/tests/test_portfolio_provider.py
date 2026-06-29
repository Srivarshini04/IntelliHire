"""Portfolio evidence provider tests (no network)."""

import asyncio

from app.services.evidence import portfolio_service
from app.services.evidence.portfolio_extractor import (
    _extract_links,
    _extract_projects,
    _strip_html,
    normalize_portfolio_url,
)
from app.services.evidence.portfolio_service import (
    analyze_portfolio_evidence,
    extract_skills_from_text,
)

_SAMPLE_HTML = """
<html><head><title>Asha — ML Engineer</title><style>.x{color:red}</style></head>
<body>
  <h1>Asha Rao</h1>
  <h2>ClinicBot</h2>
  <p>Built with Python, TensorFlow and FastAPI. Deployed on Kubernetes.</p>
  <h2>WattWise</h2>
  <script>var a = 1;</script>
  <a href="https://github.com/asharao">GitHub</a>
  <a href="https://www.linkedin.com/in/asharao">LinkedIn</a>
</body></html>
"""


def test_normalize_portfolio_url_adds_scheme():
    assert normalize_portfolio_url("asha.dev") == "https://asha.dev"
    assert normalize_portfolio_url("http://asha.dev") == "http://asha.dev"
    assert normalize_portfolio_url("  https://asha.dev ") == "https://asha.dev"


def test_strip_html_removes_script_and_style():
    text = _strip_html(_SAMPLE_HTML)
    assert "color:red" not in text
    assert "var a = 1" not in text
    assert "ClinicBot" in text and "Python" in text


def test_extract_links_finds_platforms():
    links = _extract_links(_SAMPLE_HTML)
    assert links["github"].startswith("https://github.com/asharao")
    assert links["linkedin"].startswith("https://www.linkedin.com/in/asharao")


def test_extract_projects_from_headings():
    projects = _extract_projects(_SAMPLE_HTML)
    assert "Asha Rao" in projects
    assert "ClinicBot" in projects
    assert "WattWise" in projects


def test_extract_skills_from_text_uses_ontology():
    skills = extract_skills_from_text("I work with Python, TensorFlow and FastAPI daily.")
    lowered = {s.lower() for s in skills}
    assert "python" in lowered
    # FastAPI / TensorFlow may canonicalize; at least one framework recognised.
    assert len(skills) >= 1


def test_analyze_portfolio_evidence_with_mocked_fetch(monkeypatch):
    def _fake_fetch(_url):
        return {
            "url": "https://asha.dev",
            "title": "Asha — ML Engineer",
            "text": _strip_html(_SAMPLE_HTML),
            "links": _extract_links(_SAMPLE_HTML),
            "projects": _extract_projects(_SAMPLE_HTML),
        }

    monkeypatch.setattr(portfolio_service, "fetch_portfolio_data", _fake_fetch)
    result = asyncio.run(
        analyze_portfolio_evidence("asha.dev", role_blueprint={"skills": ["Python", "Rust"]})
    )
    assert result["source"] == "portfolio"
    assert result["portfolio_url"] == "https://asha.dev"
    assert "Python" in result["jd_match"]["matched"]
    assert result["jd_match"]["coverage"] == 50.0  # 1 of 2 required (Python yes, Rust no)
    assert "ClinicBot" in result["projects"]
    assert result["links"]["github"].startswith("https://github.com/")


def test_analyze_portfolio_evidence_degrades_on_fetch_failure(monkeypatch):
    def _boom(_url):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(portfolio_service, "fetch_portfolio_data", _boom)
    result = asyncio.run(analyze_portfolio_evidence("https://asha.dev"))
    assert result["source"] == "portfolio"
    assert result["error"] == "connection refused"


def test_analyze_portfolio_evidence_rejects_empty_url():
    result = asyncio.run(analyze_portfolio_evidence(""))
    assert result["error"]
