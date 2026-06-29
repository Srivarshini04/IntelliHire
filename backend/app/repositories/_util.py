"""Small shared helpers for the persistence repositories.

The shared Pydantic models carry ids as plain strings (e.g. ``candidate_id``),
while the ORM FKs are Postgres UUIDs. These helpers coerce between the two without
leaking any business logic.
"""

from __future__ import annotations

import uuid
from typing import Any


def to_uuid(value: Any) -> uuid.UUID:
    """Coerce a shared string id (or UUID) into a UUID for an ORM FK column."""
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def enum_value(value: Any) -> Any:
    """Return ``.value`` for enum members, otherwise the value unchanged."""
    return getattr(value, "value", value)
