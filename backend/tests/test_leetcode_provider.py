"""LeetCode evidence provider + scoring engine tests (no network)."""

import asyncio

import pytest

from app.services.evidence import leetcode_service
from app.services.evidence.leetcode_engine import LeetCodeEvaluator
from app.services.evidence.leetcode_service import analyze_leetcode_evidence


def test_extract_username_from_url_variants():
    assert LeetCodeEvaluator.extract_username("https://leetcode.com/u/venu") == "venu"
    assert LeetCodeEvaluator.extract_username("https://leetcode.com/venu/") == "venu"
    assert LeetCodeEvaluator.extract_username("venu") == "venu"
    assert LeetCodeEvaluator.extract_username("https://leetcode.com/problems") is None


def test_scores_are_monotonic_in_volume():
    low = LeetCodeEvaluator.calculate_scores(50, 20, 5)
    high = LeetCodeEvaluator.calculate_scores(200, 150, 60)
    assert high["coding_skill"] > low["coding_skill"]
    assert 0 <= low["coding_skill"] <= 100
    assert 0 <= high["coding_skill"] <= 100


def test_score_capped_at_100_and_tiered():
    huge = LeetCodeEvaluator.calculate_scores(1000, 1000, 500, contest_rating=2600)
    assert huge["coding_skill"] <= 100
    assert huge["tier"] in {"Elite", "Advanced", "Proficient", "Developing", "Beginner"}


def test_contest_rating_is_bonus_only():
    without = LeetCodeEvaluator.calculate_scores(100, 80, 30)
    withc = LeetCodeEvaluator.calculate_scores(100, 80, 30, contest_rating=2100)
    assert withc["coding_skill"] >= without["coding_skill"]
    assert withc["contest_bonus"] > 0


def _fake_eval(_url):
    return {
        "username": "venu",
        "easy_solved": 100,
        "medium_solved": 150,
        "hard_solved": 50,
        "total_solved": 300,
        "ranking": 50000,
        "acceptance_rate": 62.0,
        "contest_rating": 1800,
        "volume": 80.0,
        "mastery": 75.0,
        "hard_depth": 60.0,
        "balance": 70.0,
        "contest_bonus": 2.0,
        "coding_skill": 74.0,
        "tier": "Advanced",
        "strengths": ["Strong medium-level problem solving"],
        "improvements": ["Solve more hard problems"],
        "coverage": {"easy": 20.0, "medium": 18.0, "hard": 8.0},
    }


def test_analyze_leetcode_evidence_wraps_engine(monkeypatch):
    monkeypatch.setattr(leetcode_service.LeetCodeEvaluator, "evaluate", staticmethod(_fake_eval))
    result = asyncio.run(analyze_leetcode_evidence("https://leetcode.com/u/venu"))
    assert result["source"] == "leetcode"
    assert result["source_url"] == "https://leetcode.com/u/venu"
    assert result["coding_skill"] == 74.0
    assert result["tier"] == "Advanced"
    assert "error" not in result


def test_analyze_leetcode_evidence_degrades_on_failure(monkeypatch):
    def _boom(_url):
        raise ValueError("LeetCode user not found")

    monkeypatch.setattr(leetcode_service.LeetCodeEvaluator, "evaluate", staticmethod(_boom))
    result = asyncio.run(analyze_leetcode_evidence("https://leetcode.com/u/ghost"))
    assert result["source"] == "leetcode"
    assert result["error"] == "LeetCode user not found"


def test_analyze_leetcode_evidence_rejects_empty_url():
    result = asyncio.run(analyze_leetcode_evidence("   "))
    assert result["error"]


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-q"])
