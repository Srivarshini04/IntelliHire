#!/usr/bin/env python3
"""CLI for GitHub evidence extraction — teammate workflow + deep pipeline."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.evidence.github_extractor import fetch_github_data
from app.services.evidence.skill_extractor import extract_skills


def run_basic(github_url: str) -> dict:
    github_data = fetch_github_data(github_url)
    skills = extract_skills(github_data)
    return {
        "profile": github_data["profile"],
        "skills": skills,
        "repos": github_data["repos"],
        "git_activity": github_data["events"],
    }


if __name__ == "__main__":
    default_url = "https://github.com/Anushakaringula"
    github_url = sys.argv[1] if len(sys.argv) > 1 else default_url
    print(f"Analyzing: {github_url}")
    print(json.dumps(run_basic(github_url), indent=2))
