import asyncio

from app.documents.service import build_document
from app.intelligence.resume.profile_orchestrator import ResumeProfileOrchestrator
from app.intelligence.resume.url_extractor import extract_urls


def _pdf_bytes_with_text(text: str) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    return doc.tobytes()


def test_url_extractor_detects_platforms():
    text = (
        "GitHub: https://github.com/venu\n"
        "LinkedIn: https://www.linkedin.com/in/venu\n"
        "LeetCode: https://leetcode.com/u/venu\n"
        "Portfolio: https://venu.dev"
    )
    urls = extract_urls(text)
    assert urls["github_url"].startswith("https://github.com/")
    assert urls["linkedin_url"].startswith("https://www.linkedin.com/in/")
    assert urls["leetcode_url"].startswith("https://leetcode.com/")
    assert urls["portfolio_url"] == "https://venu.dev"


def test_resume_orchestrator_heuristic_profile_without_llm():
    resume_text = (
        "Venu Nugula\n"
        "venu@example.com\n"
        "+91 9876543210\n"
        "Python, TensorFlow, Kubernetes\n"
        "https://github.com/venu\n"
        "https://www.linkedin.com/in/venu\n"
    )
    content = _pdf_bytes_with_text(resume_text)
    document = build_document("resume.pdf", content)

    orchestrator = ResumeProfileOrchestrator(db=None)
    profile, telemetry = asyncio.run(orchestrator.run(document))

    assert profile.name.value
    assert profile.email is not None
    assert any(s.skill_id for s in profile.skills)
    assert profile.github_url is not None
    assert profile.linkedin_url is not None
    assert telemetry.average_confidence > 0
