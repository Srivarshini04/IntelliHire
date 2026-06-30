"""Evidence Ledger — the centralized, immutable record of every claim + proof.

The ledger is the system of record for the Graph Intelligence Layer. Every
``Evidence`` emitted by a provider is appended here exactly once and never
mutated. Downstream engines (entity resolution, fusion, inference) read from the
ledger; they never edit a stored entry. When evidence is bound to a graph node
it is *promoted* to an ``EvidenceLedgerEntry`` (a new object) — the original raw
``Evidence`` stays untouched.

Design notes
------------
* **Immutable entries** — stored ``Evidence`` is deep-copied on insert and handed
  back as copies, so callers cannot mutate the ledger's internal state.
* **Full provenance** — each ``Evidence`` already carries ``provenance`` +
  ``source`` + ``source_span`` + ``collected_at``; the ledger preserves them and
  never strips them.
* **Queryable** — by candidate, source, entity (canonical ref), evidence type,
  and (once bound) by supporting graph node.

This is an in-memory implementation. It is deliberately backend-agnostic: a
future implementation can persist to the ``evidence_ledger`` table via
``app.models.ledger`` without changing this interface.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Iterable

from app.shared.enums import EvidenceSource, EvidenceType
from app.shared.models.evidence import Evidence, EvidenceLedgerEntry

logger = logging.getLogger(__name__)


class DuplicateEvidenceError(ValueError):
    """Raised when an ``evidence_id`` already exists in the ledger."""


class EvidenceLedger:
    """Append-only, immutable store of ``Evidence`` keyed by ``evidence_id``.

    Thread-safety is intentionally out of scope: build one ledger per
    candidate-graph build, which is a single logical unit of work.
    """

    def __init__(self) -> None:
        self._by_id: dict[str, Evidence] = {}
        # Secondary indexes for O(1) lookups (store ids, resolve to copies on read).
        self._by_candidate: dict[str, list[str]] = defaultdict(list)
        self._by_entity: dict[str, list[str]] = defaultdict(list)
        self._by_source: dict[EvidenceSource, list[str]] = defaultdict(list)
        self._by_type: dict[EvidenceType, list[str]] = defaultdict(list)

    # --- writes (append-only) ------------------------------------------------

    def add(self, evidence: Evidence) -> EvidenceLedgerEntry:
        """Append one immutable evidence record. Returns an unbound ledger entry.

        Raises ``DuplicateEvidenceError`` if the ``evidence_id`` is already present
        (ledger entries are immutable — re-adding is a programming error, not an
        update). Use :meth:`add_all` for bulk ingest that tolerates duplicates.
        """
        if evidence.evidence_id in self._by_id:
            raise DuplicateEvidenceError(
                f"evidence_id {evidence.evidence_id!r} already in ledger"
            )

        stored = evidence.model_copy(deep=True)
        self._by_id[stored.evidence_id] = stored
        self._by_candidate[stored.candidate_id].append(stored.evidence_id)
        self._by_entity[stored.entity_ref].append(stored.evidence_id)
        self._by_source[stored.source].append(stored.evidence_id)
        self._by_type[stored.evidence_type].append(stored.evidence_id)

        logger.debug(
            "ledger.add id=%s source=%s entity=%s conf=%.2f",
            stored.evidence_id, stored.source.value, stored.entity_ref, stored.confidence,
        )
        # Unbound entry — supporting_node_id is filled when the GraphBuilder binds it.
        return EvidenceLedgerEntry.from_evidence(stored, supporting_node_id=stored.entity_ref)

    def add_all(self, evidence: Iterable[Evidence], *, skip_duplicates: bool = True) -> int:
        """Bulk-append. Returns the number actually added.

        Duplicate ``evidence_id``s are skipped (logged) unless ``skip_duplicates``
        is False, in which case the first duplicate raises.
        """
        added = 0
        for ev in evidence:
            if ev.evidence_id in self._by_id:
                if skip_duplicates:
                    logger.warning("ledger.add_all skipping duplicate id=%s", ev.evidence_id)
                    continue
                raise DuplicateEvidenceError(ev.evidence_id)
            self.add(ev)
            added += 1
        return added

    # --- reads (always return copies; the store stays immutable) -------------

    def get(self, evidence_id: str) -> Evidence | None:
        ev = self._by_id.get(evidence_id)
        return ev.model_copy(deep=True) if ev else None

    def all(self) -> list[Evidence]:
        return [ev.model_copy(deep=True) for ev in self._by_id.values()]

    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, evidence_id: object) -> bool:
        return evidence_id in self._by_id

    def by_candidate(self, candidate_id: str) -> list[Evidence]:
        return self._resolve(self._by_candidate.get(candidate_id, []))

    def by_entity(self, entity_ref: str) -> list[Evidence]:
        """All evidence about one canonical entity (the fusion/dedup key)."""
        return self._resolve(self._by_entity.get(entity_ref, []))

    def by_source(self, source: EvidenceSource) -> list[Evidence]:
        return self._resolve(self._by_source.get(source, []))

    def by_type(self, evidence_type: EvidenceType) -> list[Evidence]:
        return self._resolve(self._by_type.get(evidence_type, []))

    def confidence_pairs(self, entity_ref: str) -> list[tuple[str, float]]:
        """``(source, confidence)`` tuples for one entity — the fusion-engine input."""
        return [(ev.source.value, ev.confidence) for ev in self.by_entity(entity_ref)]

    def sources_for(self, entity_ref: str) -> set[EvidenceSource]:
        """Distinct sources that attest one entity (claim-strength / corroboration)."""
        return {ev.source for ev in self.by_entity(entity_ref)}

    # --- internal ------------------------------------------------------------

    def _resolve(self, ids: list[str]) -> list[Evidence]:
        return [self._by_id[i].model_copy(deep=True) for i in ids]
