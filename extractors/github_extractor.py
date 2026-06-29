import requests
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("GITHUB_TOKEN")

if not TOKEN:
    raise Exception("GITHUB_TOKEN missing in .env")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json"
}


def parse_github_url(github_url):
    parts = github_url.rstrip("/").replace("https://github.com/", "").split("/")

    if len(parts) == 1:
        return {
            "username": parts[0],
            "repo": None
        }

    return {
        "username": parts[0],
        "repo": parts[1]
    }


def fetch_languages(username, repo_name):
    url = f"https://api.github.com/repos/{username}/{repo_name}/languages"

    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        return {}

    return response.json()


def fetch_commit_count(username, repo_name):
    url = f"https://api.github.com/repos/{username}/{repo_name}/commits"

    # per_page=1 makes the last page number equal the total commit count
    params = {"author": username, "per_page": 1}

    response = requests.get(url, headers=HEADERS, params=params)

    if response.status_code != 200:
        return 0

    # When paginated, GitHub puts the last page number in the Link header
    link = response.headers.get("Link", "")
    match = re.search(r'[?&]page=(\d+)>;\s*rel="last"', link)
    if match:
        return int(match.group(1))

    # No Link header means a single page: 0 or 1 commits
    return len(response.json())


def fetch_recent_events(username):
    url = f"https://api.github.com/users/{username}/events"

    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        return []

    events = response.json()

    # Collapse multiple events on the same repo into a single entry.
    activity = {}

    for event in events:
        repo = event.get("repo", {}).get("name")
        if not repo:
            continue

        # "owned" repos belong to this person; otherwise they only contributed
        # to it (repo name is "owner/repo").
        owned = repo.split("/")[0].lower() == username.lower()

        payload = event.get("payload", {})

        commit_count = 0
        if event["type"] == "PushEvent":
            commit_count = len(payload.get("commits", []))

        if repo not in activity:
            activity[repo] = {
                "repo": repo,
                "owned": owned,
                "event_count": 0,
                "commit_count": 0,
                "last_active": event["created_at"]
            }

        activity[repo]["event_count"] += 1
        activity[repo]["commit_count"] += commit_count
        # Events come newest-first, so the first one seen is the latest
        if event["created_at"] > activity[repo]["last_active"]:
            activity[repo]["last_active"] = event["created_at"]

    # Most recently active repos first
    return sorted(
        activity.values(),
        key=lambda a: a["last_active"],
        reverse=True
    )


def build_repo_info(username, repo):
    repo_name = repo.get("name")

    languages = fetch_languages(username, repo_name)
    commit_count = fetch_commit_count(username, repo_name)

    return {
        "name": repo_name,
        "description": repo.get("description") or "",
        "language": repo.get("language") or "",
        "topics": repo.get("topics", []),
        "stars": repo.get("stargazers_count", 0),
        "forks": repo.get("forks_count", 0),
        "updated_at": repo.get("updated_at"),
        "url": repo.get("html_url"),
        "languages": languages,
        "commit_count": commit_count
    }


def fetch_github_data(github_url):
    parsed = parse_github_url(github_url)

    username = parsed["username"]

    profile_url = f"https://api.github.com/users/{username}"
    repos_url = f"https://api.github.com/users/{username}/repos"

    profile_response = requests.get(profile_url, headers=HEADERS)
    repos_response = requests.get(repos_url, headers=HEADERS)

    if profile_response.status_code != 200:
        print("Profile fetch failed:", profile_response.json())
        return {
            "profile": {},
            "repos": [],
            "events": []
        }

    profile = profile_response.json()
    repos = repos_response.json()

    if not isinstance(repos, list):
        print("Repo fetch failed:", repos)
        return {
            "profile": {},
            "repos": [],
            "events": []
        }

    print(f"Fetching {len(repos)} repos for {username} ...")

    # Each repo needs its own API calls (languages + commit count);
    # run them in parallel so we don't wait for them one by one.
    with ThreadPoolExecutor(max_workers=10) as executor:
        repo_data = list(
            executor.map(lambda r: build_repo_info(username, r), repos)
        )

    recent_events = fetch_recent_events(username)

    return {
        "profile": {
            "name": profile.get("name"),
            "bio": profile.get("bio"),
            "followers": profile.get("followers"),
            "following": profile.get("following"),
            "public_repos": profile.get("public_repos"),
            "created_at": profile.get("created_at")
        },
        "repos": repo_data,
        "events": recent_events
    }
