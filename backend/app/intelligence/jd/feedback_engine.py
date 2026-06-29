"""Compute structured diffs between AI blueprint and recruiter edits."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.job import RoleBlueprint


class FieldDiff(BaseModel):
    field: str
    added: list = Field(default_factory=list)
    removed: list = Field(default_factory=list)
    modified: list = Field(default_factory=list)


class FeedbackSummary(BaseModel):
    document_id: str
    draft_artifact_id: str | None = None
    fields_changed: list[str] = Field(default_factory=list)
    diffs: list[FieldDiff] = Field(default_factory=list)
    total_changes: int = 0


class FeedbackEngine:
    @classmethod
    def compute_diff(cls, ai_blueprint: RoleBlueprint, human_blueprint: RoleBlueprint) -> FeedbackSummary:
        diffs: list[FieldDiff] = []
        fields_changed: list[str] = []

        scalar_fields = [
            ("role_title", ai_blueprint.role_title.value, human_blueprint.role_title.value),
            (
                "experience_level",
                ai_blueprint.experience_level.value,
                human_blueprint.experience_level.value,
            ),
        ]

        for field_name, ai_val, human_val in scalar_fields:
            if ai_val != human_val:
                fields_changed.append(field_name)
                diffs.append(
                    FieldDiff(
                        field=field_name,
                        modified=[{"from": ai_val, "to": human_val}],
                    )
                )

        skill_diff = cls._diff_skill_lists(
            "required_skills",
            [s.normalized_name for s in ai_blueprint.required_skills],
            [s.normalized_name for s in human_blueprint.required_skills],
        )
        if skill_diff:
            fields_changed.append("required_skills")
            diffs.append(skill_diff)

        pref_diff = cls._diff_skill_lists(
            "preferred_skills",
            [s.normalized_name for s in ai_blueprint.preferred_skills],
            [s.normalized_name for s in human_blueprint.preferred_skills],
        )
        if pref_diff:
            fields_changed.append("preferred_skills")
            diffs.append(pref_diff)

        weights_diff = cls._diff_weights(
            ai_blueprint.capability_weights,
            human_blueprint.capability_weights,
        )
        if weights_diff:
            fields_changed.append("capability_weights")
            diffs.append(weights_diff)

        return FeedbackSummary(
            document_id="",
            fields_changed=fields_changed,
            diffs=diffs,
            total_changes=sum(
                len(d.added) + len(d.removed) + len(d.modified) for d in diffs
            ),
        )

    @staticmethod
    def _diff_skill_lists(field: str, ai_skills: list[str], human_skills: list[str]) -> FieldDiff | None:
        ai_set = set(ai_skills)
        human_set = set(human_skills)
        added = sorted(human_set - ai_set)
        removed = sorted(ai_set - human_set)
        if not added and not removed:
            return None
        return FieldDiff(field=field, added=added, removed=removed)

    @staticmethod
    def _diff_weights(ai_weights: dict[str, float], human_weights: dict[str, float]) -> FieldDiff | None:
        if ai_weights == human_weights:
            return None
        modified = []
        all_keys = set(ai_weights) | set(human_weights)
        for key in sorted(all_keys):
            if ai_weights.get(key) != human_weights.get(key):
                modified.append({
                    "key": key,
                    "from": ai_weights.get(key),
                    "to": human_weights.get(key),
                })
        return FieldDiff(field="capability_weights", modified=modified) if modified else None
