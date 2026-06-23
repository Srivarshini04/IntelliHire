"""GitHub Parser — Member 2: feat/github-parser"""


async def parse_github(github_url: str) -> dict:
    """Extract repos, languages, commit stats, stars, deployments."""
    return {
        "repositories": [],
        "languages": [],
        "commit_stats": [],
        "stars": [],
        "deployments": [],
    }
