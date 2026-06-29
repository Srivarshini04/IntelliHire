"""Persistence repositories for the DELULU v2 tables.

One class per aggregate. Each repository is *persistence only* — no business logic,
no reasoning. They map between the frozen shared Pydantic models
(``app.shared.models.*``) and the ORM mirror rows (``app.models.*``) via ``to_orm`` /
``from_orm`` helpers, and expose async ``create`` / ``get_by_domain_id`` /
``list_for_candidate`` / ``list_for_job`` / ``upsert`` methods over an
``AsyncSession`` (the session pattern from ``app.core.database``).
"""

from app.repositories.decision import DecisionRepository
from app.repositories.graph import CandidateGraphRepository
from app.repositories.ledger import EvidenceLedgerRepository
from app.repositories.ranking import RankingRepository
from app.repositories.reasoning import ReasoningRepository

__all__ = [
    "EvidenceLedgerRepository",
    "CandidateGraphRepository",
    "ReasoningRepository",
    "DecisionRepository",
    "RankingRepository",
]
