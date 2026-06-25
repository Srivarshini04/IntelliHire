"""Phase 8 — Capability Engine."""

from __future__ import annotations

from dataclasses import dataclass, field

CAPABILITY_GRAPH: dict[str, dict[str, float]] = {
    "backend_engineering": {
        "api_layer": 0.25,
        "auth_layer": 0.15,
        "database_layer": 0.2,
        "background_jobs": 0.15,
        "caching": 0.1,
        "testing": 0.15,
    },
    "database_engineering": {
        "database_layer": 0.5,
        "caching": 0.15,
        "backend_engineering_skill": 0.2,
        "testing": 0.15,
    },
    "deployment_engineering": {
        "devops": 0.5,
        "backend_engineering_skill": 0.25,
        "testing": 0.25,
    },
    "frontend_engineering": {
        "react_skill": 0.4,
        "testing": 0.2,
        "api_layer": 0.2,
        "devops": 0.2,
    },
}

SKILL_TO_CAPABILITY: dict[str, list[str]] = {
    "FastAPI": ["backend_engineering"],
    "PostgreSQL": ["database_engineering", "backend_engineering"],
    "AWS": ["deployment_engineering", "backend_engineering"],
    "Redis": ["backend_engineering", "database_engineering"],
    "Docker": ["deployment_engineering"],
    "pytest": ["backend_engineering"],
    "React": ["frontend_engineering"],
    "Node.js": ["backend_engineering"],
}


@dataclass
class RepoSignals:
    architecture_layers: dict[str, bool] = field(default_factory=dict)
    pattern_depths: dict[str, float] = field(default_factory=dict)
    complexity_score: float = 0.0
    git_consistency: float = 0.0
    git_ownership: float = 0.0
    months_active: float = 0.0
    dependencies: set[str] = field(default_factory=set)


def _layer_score(layers: dict[str, bool], layer: str) -> float:
    return 100.0 if layers.get(layer) else 0.0


def _skill_score(signals: RepoSignals, skill: str) -> float:
    depth = signals.pattern_depths.get(skill, 0.0) * 100
    dep_bonus = 20.0 if skill.lower() in {d.lower() for d in signals.dependencies} else 0.0
    complexity_bonus = min(signals.complexity_score, 20.0)
    git_bonus = min(signals.git_consistency * 5 + signals.git_ownership * 15, 20.0)
    longevity_bonus = min(signals.months_active * 2, 15.0)

    raw = depth * 0.45 + dep_bonus + complexity_bonus + git_bonus + longevity_bonus
    return min(raw, 100.0)


def _complexity_from_features(features: dict) -> float:
    loc = features.get("lines_of_code", 0)
    modules = features.get("module_count", 0)
    dirs = features.get("directory_count", 0)
    loc_score = min(loc / 5000, 1.0) * 10
    mod_score = min(modules / 10, 1.0) * 5
    dir_score = min(dirs / 20, 1.0) * 5
    return loc_score + mod_score + dir_score


def aggregate_repo_signals(
    architecture_layers: dict[str, bool],
    pattern_results: dict,
    complexity_features: dict,
    git_metrics: dict,
    dependencies: set[str],
) -> RepoSignals:
    git_consistency = min(git_metrics.get("commits_per_month", 0) / 10, 1.0)
    return RepoSignals(
        architecture_layers=architecture_layers,
        pattern_depths={k: v.depth if hasattr(v, "depth") else v.get("depth", 0) for k, v in pattern_results.items()},
        complexity_score=_complexity_from_features(complexity_features),
        git_consistency=git_consistency,
        git_ownership=git_metrics.get("candidate_commit_share", 0),
        months_active=git_metrics.get("months_active", 0),
        dependencies=dependencies,
    )


def compute_capability_scores(
    repo_signals_list: list[RepoSignals],
    skill_scores: dict[str, float],
) -> dict[str, int]:
    if not repo_signals_list:
        return {cap: 0 for cap in CAPABILITY_GRAPH}

    merged_layers: dict[str, float] = {}
    for signals in repo_signals_list:
        for layer, present in signals.architecture_layers.items():
            merged_layers[layer] = max(merged_layers.get(layer, 0), 100.0 if present else 0.0)

    backend_skill = max(
        skill_scores.get("FastAPI", 0),
        skill_scores.get("Node.js", 0),
        0,
    )
    react_skill = skill_scores.get("React", 0)

    capabilities: dict[str, int] = {}
    for capability, weights in CAPABILITY_GRAPH.items():
        total = 0.0
        weight_sum = 0.0
        for component, weight in weights.items():
            if component == "backend_engineering_skill":
                total += backend_skill * weight
            elif component == "react_skill":
                total += react_skill * weight
            else:
                total += merged_layers.get(component, 0.0) * weight
            weight_sum += weight
        score = total / weight_sum if weight_sum else 0.0
        capabilities[capability] = int(round(min(score, 100)))

    return capabilities


def compute_skill_scores(
    repo_signals_list: list[RepoSignals],
    jd_skills: list[str],
    all_pattern_skills: set[str],
) -> dict[str, int]:
    skills = set(jd_skills) | all_pattern_skills
    scores: dict[str, float] = {}

    for skill in skills:
        skill_values = []
        for signals in repo_signals_list:
            skill_values.append(_skill_score(signals, skill))
        scores[skill] = max(skill_values) if skill_values else 0.0

    return {skill: int(round(score)) for skill, score in scores.items()}
