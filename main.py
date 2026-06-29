from extractors.github_extractor import fetch_github_data
from analyzers.skill_extractor import extract_skills
import sys
import json


def run_engine(github_url):
    github_data = fetch_github_data(github_url)

    skills = extract_skills(github_data)

    evidence = {
        "profile": github_data["profile"],
        "skills": skills,
        "repos": github_data["repos"],
        "git_activity": github_data["events"]
    }

    return evidence


if __name__ == "__main__":
    # Pass a profile URL as an argument, e.g.
    #     python3 main.py https://github.com/some-user
    # If none is given, the default profile below is used.
    default_url = "https://github.com/Anushakaringula"

    github_url = sys.argv[1] if len(sys.argv) > 1 else default_url

    print(f"Analyzing: {github_url}")

    result = run_engine(github_url)

    print(json.dumps(result, indent=4))
