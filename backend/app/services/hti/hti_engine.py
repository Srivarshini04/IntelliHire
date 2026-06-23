"""Hidden Talent Engine — HTI = Capability - Visibility (normalized 0-100)."""


async def compute_hti(capability_score: float, visibility_signals: dict) -> dict:
    visibility = 0.0
    hti = max(0.0, min(100.0, capability_score - visibility))
    return {"visibility_score": visibility, "hti_score": hti}
