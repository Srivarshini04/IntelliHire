"""Blueprint Diff — semantic diff when JD is revised."""

from __future__ import annotations

from app.schemas.artifacts import BlueprintDiff, BlueprintDiffItem
from app.schemas.job import RoleBlueprint


def diff_blueprints(old: RoleBlueprint, new: RoleBlueprint) -> BlueprintDiff:
    changes: list[BlueprintDiffItem] = []

    if old.role_title.value != new.role_title.value:
        changes.append(BlueprintDiffItem(
            field="role_title",
            change_type="modified",
            old_value=old.role_title.value,
            new_value=new.role_title.value,
        ))

    if old.experience_level.value != new.experience_level.value:
        changes.append(BlueprintDiffItem(
            field="experience_level",
            change_type="modified",
            old_value=old.experience_level.value,
            new_value=new.experience_level.value,
        ))

    old_skills = {s.normalized_name for s in old.required_skills}
    new_skills = {s.normalized_name for s in new.required_skills}
    for skill in new_skills - old_skills:
        changes.append(BlueprintDiffItem(field="required_skills", change_type="added", new_value=skill))
    for skill in old_skills - new_skills:
        changes.append(BlueprintDiffItem(field="required_skills", change_type="removed", old_value=skill))

    summary_parts = []
    if changes:
        summary_parts.append(f"{len(changes)} field(s) changed")
    else:
        summary_parts.append("No significant changes")

    return BlueprintDiff(
        changes=changes,
        summary="; ".join(summary_parts),
    )
