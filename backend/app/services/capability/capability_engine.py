"""Capability Engine — Member 1: feat/scoring-engine

Capability = 0.30×Technical + 0.30×Execution + 0.20×Ownership + 0.20×Learning
"""


async def compute_capability(evidence: dict, role_blueprint: dict) -> dict:
    return {
        "technical": 0.0,
        "execution": 0.0,
        "ownership": 0.0,
        "learning_velocity": 0.0,
        "problem_solving": 0.0,
        "domain_expertise": 0.0,
        "capability_score": 0.0,
    }
