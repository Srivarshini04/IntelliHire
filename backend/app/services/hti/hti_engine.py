"""Hidden Talent Engine — HTI from capability vs visibility signals."""


async def compute_hti(capability_score: float, visibility_signals: dict) -> dict:
    github = visibility_signals.get("github") or {}
    basic = github.get("basic") or {}
    deep = github.get("deep") or {}
    profile = basic.get("profile") or {}
    impact = deep.get("project_impact") or {}
    hidden_gem = github.get("hidden_gem") or deep.get("hidden_gem") or {}

    followers = float(profile.get("followers") or 0)
    total_stars = float(impact.get("total_stars") or 0)
    max_stars = float(impact.get("max_repo_stars") or 0)

    prestige_signal = min(followers / 50, 30) + min(total_stars / 100, 40) + min(max_stars / 50, 30)
    visibility = min(prestige_signal, 100.0)

    if hidden_gem.get("hidden_gem"):
        hti = max(capability_score - visibility + 15, capability_score * 0.7)
    else:
        hti = max(0.0, min(100.0, capability_score - visibility))

    return {
        "visibility_score": round(visibility, 1),
        "hti_score": round(min(hti, 100.0), 1),
    }
