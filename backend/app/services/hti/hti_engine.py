"""Hidden Talent Engine — HTI from capability vs visibility signals."""


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


async def compute_hti(capability_score: float, visibility_signals: dict) -> dict:
    github = visibility_signals.get("github") or {}
    basic = github.get("basic") or {}
    deep = github.get("deep") or {}
    profile = basic.get("profile") or {}
    impact = deep.get("project_impact") or {}
    hidden_gem = github.get("hidden_gem") or deep.get("hidden_gem") or {}

    linkedin = visibility_signals.get("linkedin") or {}
    li_profile = (linkedin.get("basic") or {}).get("profile") or linkedin.get("profile") or {}

    followers = float(profile.get("followers") or 0)
    total_stars = float(impact.get("total_stars") or 0)
    max_stars = float(impact.get("max_repo_stars") or 0)

    # LinkedIn audience is a public-visibility signal (caps keep it modest vs. GitHub impact).
    li_followers = _num(li_profile.get("followers"))
    li_connections = _num(li_profile.get("connections"))
    linkedin_visibility = min(li_followers / 100, 20) + min(li_connections / 500, 20)

    prestige_signal = min(followers / 50, 30) + min(total_stars / 100, 40) + min(max_stars / 50, 30)
    visibility = min(prestige_signal + linkedin_visibility, 100.0)

    if hidden_gem.get("hidden_gem"):
        hti = max(capability_score - visibility + 15, capability_score * 0.7)
    else:
        hti = max(0.0, min(100.0, capability_score - visibility))

    return {
        "visibility_score": round(visibility, 1),
        "hti_score": round(min(hti, 100.0), 1),
    }
