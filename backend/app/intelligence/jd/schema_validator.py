"""Pydantic schema validation with retry."""

from __future__ import annotations

import logging

from pydantic import ValidationError

from app.intelligence.jd.blueprint_llm_schema import BlueprintLLMOutput

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


class SchemaValidationError(Exception):
    def __init__(self, errors: list[str], attempts: int):
        self.errors = errors
        self.attempts = attempts
        super().__init__(f"Schema validation failed after {attempts} attempts: {errors}")


def validate_llm_output(data: dict) -> BlueprintLLMOutput:
    """First gate: Pydantic validation. Do not silently repair."""
    return BlueprintLLMOutput.model_validate(data)


async def validate_with_retry(
    extract_fn,
    *args,
    **kwargs,
) -> tuple[BlueprintLLMOutput, int]:
    """
    Retry extraction up to MAX_RETRIES on validation failure.
    extract_fn must be async callable returning BlueprintLLMOutput.
    """
    last_errors: list[str] = []
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            result = await extract_fn(*args, **kwargs)
            # Re-validate through model round-trip
            validated = BlueprintLLMOutput.model_validate(result.model_dump())
            return validated, attempt - 1
        except (ValidationError, ValueError) as exc:
            last_errors = [str(exc)]
            logger.warning("Blueprint schema validation attempt %d failed: %s", attempt, exc)
    raise SchemaValidationError(last_errors, MAX_RETRIES + 1)
