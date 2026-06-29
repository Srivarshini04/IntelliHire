"""Approval-time validation — reuses ValidationEngine confidence gates."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.intelligence.validation import ValidationEngine, ValidationResult
from app.schemas.job import RoleBlueprint


class ApprovalValidationResult(BaseModel):
    passed: bool = True
    validation: ValidationResult = Field(default_factory=ValidationResult)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ApprovalValidator:
    """Validate recruiter-submitted blueprint before approval."""

    @classmethod
    def validate(
        cls,
        blueprint: RoleBlueprint,
        confirmations: list[str] | None = None,
    ) -> ApprovalValidationResult:
        validation = ValidationEngine.validate_blueprint(blueprint, confirmations)

        errors = list(validation.errors)
        warnings = list(validation.warnings)

        if not blueprint.role_title.value.strip():
            errors.append("role_title is required")
        if not blueprint.required_skills:
            errors.append("required_skills must not be empty")

        weights = blueprint.capability_weights
        if weights:
            total = sum(weights.values())
            if abs(total - 1.0) > 0.01:
                errors.append(f"capability_weights must sum to 1.0, got {total}")

        passed = len(errors) == 0 and validation.passed

        return ApprovalValidationResult(
            passed=passed,
            validation=validation,
            warnings=warnings,
            errors=errors,
        )
