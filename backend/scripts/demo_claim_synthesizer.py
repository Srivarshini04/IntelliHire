"""Temporary local script — manual ClaimSynthesizer verification.

Loads mock_graph.json and mock_job.json, runs ClaimSynthesizer only, and prints
claim output. Independent of FastAPI / runtime / APIs.

Usage (from backend/):

    py scripts/test_claim_synthesizer.py
    py scripts/test_claim_synthesizer.py --json
    py scripts/test_claim_synthesizer.py --compare
    py scripts/test_claim_synthesizer.py --json --compare
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.intelligence.reasoning.claim_synthesizer import ClaimSynthesizer
from app.intelligence.reasoning.types import MaterialityMap
from app.mock import load
from app.shared.enums import Intensity
from app.shared.models import CandidateGraph, CandidateReasoning, ReasoningClaim, RoleDNA

_SEPARATOR = "=" * 50
_RULE = "-" * 50

_MATERIALITY_LABELS = (
    Intensity.CRITICAL,
    Intensity.HIGH,
    Intensity.MEDIUM,
    Intensity.LOW,
    Intensity.NONE,
)


def _configure_stdout() -> None:
    """Prefer UTF-8 so compare markers render on Windows terminals."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


def _compare_status(match: bool, detail: str = "") -> str:
    ok, fail = "\u2713", "\u2717"
    label = "MATCH" if match else "DIFFERENCE"
    suffix = f"  {detail}" if detail else ""
    line = f"  {ok if match else fail} {label}{suffix}"
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        line.encode(encoding)
        return line
    except (UnicodeEncodeError, LookupError):
        marker = "[+]" if match else "[X]"
        return f"  {marker} {label}{suffix}"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Local ClaimSynthesizer verification (no FastAPI / runtime).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Append generated claims as formatted JSON after the human-readable output.",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare structural claim fields against mock_reasoning.json.",
    )
    return parser.parse_args(argv)


def _load_graph() -> CandidateGraph:
    return CandidateGraph.model_validate(load("mock_graph"))


def _load_role() -> RoleDNA:
    job = load("mock_job")
    return RoleDNA.model_validate(job["role_dna"])


def _load_expected_reasoning() -> CandidateReasoning:
    return CandidateReasoning.model_validate(load("mock_reasoning"))


def _format_list(values: list[str]) -> str:
    return ", ".join(values) if values else "(none)"


def _print_header(graph: CandidateGraph, role: RoleDNA) -> None:
    print("ClaimSynthesizer - local verification")
    print(f"Graph:  {graph.graph_id}")
    print(f"Role:   {role.role_dna_id} ({role.job_id})")
    print(f"Nodes:  {len(graph.nodes)}  |  Ledger entries: {len(graph.evidence_ledger)}")
    print()


def _print_claim(claim: ReasoningClaim) -> None:
    print(_SEPARATOR)
    print(f"Claim ID:            {claim.claim_id}")
    print(f"Materiality:         {claim.materiality.value}")
    print(f"Confidence:          {claim.confidence:.2f}")
    print(f"Statement:           {claim.statement}")
    print(f"Conclusion:          {claim.conclusion}")
    print(f"Entity References:   {_format_list(claim.entity_refs)}")
    print(f"Supporting Evidence: {_format_list(claim.supporting_evidence_ids)}")
    print(f"Counter Evidence:    {_format_list(claim.counter_evidence_ids)}")
    print(_RULE)


def _print_timing(elapsed_ms: float) -> None:
    print()
    print(f"ClaimSynthesizer completed in {elapsed_ms:.0f} ms.")
    print()


def _count_materiality(claims: list[ReasoningClaim]) -> Counter[Intensity]:
    counts: Counter[Intensity] = Counter()
    for claim in claims:
        counts[claim.materiality] += 1
    return counts


def _claims_with_contradictions(claims: list[ReasoningClaim]) -> int:
    return sum(1 for claim in claims if claim.counter_evidence_ids)


def _claims_with_multiple_evidence_sources(claims: list[ReasoningClaim]) -> int:
    return sum(1 for claim in claims if len(claim.supporting_evidence_ids) >= 2)


def _print_summary(claims: list[ReasoningClaim]) -> None:
    counts = _count_materiality(claims)
    print("Summary")
    print(_RULE)
    print(f"Claims Generated: {len(claims)}")
    for level in _MATERIALITY_LABELS:
        if counts[level]:
            print(f"{level.value.capitalize()}: {counts[level]}")
    print(f"Claims with contradictions: {_claims_with_contradictions(claims)}")
    print(
        "Claims with multiple evidence sources: "
        f"{_claims_with_multiple_evidence_sources(claims)}"
    )
    print()


def _print_json(claims: list[ReasoningClaim]) -> None:
    payload = [claim.model_dump(mode="json") for claim in claims]
    print("JSON output")
    print(_RULE)
    print(json.dumps(payload, indent=2))
    print()


def _structural_fields_match(actual: ReasoningClaim, expected: ReasoningClaim) -> bool:
    return (
        actual.claim_id == expected.claim_id
        and actual.entity_refs == expected.entity_refs
        and sorted(actual.supporting_evidence_ids)
        == sorted(expected.supporting_evidence_ids)
        and sorted(actual.counter_evidence_ids)
        == sorted(expected.counter_evidence_ids)
    )


def _print_compare(
    actual_by_id: dict[str, ReasoningClaim],
    expected_by_id: dict[str, ReasoningClaim],
) -> bool:
    """Print per-claim structural comparison. Returns True if all match."""
    print("Fixture comparison (mock_reasoning.json)")
    print(_RULE)
    print("(Wording, confidence, and materiality are ignored.)")
    print()

    all_match = True
    claim_ids = sorted(set(actual_by_id) | set(expected_by_id))

    for claim_id in claim_ids:
        actual = actual_by_id.get(claim_id)
        expected = expected_by_id.get(claim_id)

        if actual is None:
            print(f"{claim_id}")
            print(_compare_status(False, "(missing from synthesizer output)"))
            all_match = False
            print()
            continue
        if expected is None:
            print(f"{claim_id}")
            print(_compare_status(False, "(not present in mock_reasoning.json)"))
            all_match = False
            print()
            continue

        if _structural_fields_match(actual, expected):
            print(f"{claim_id}")
            print(_compare_status(True))
        else:
            all_match = False
            print(f"{claim_id}")
            print(_compare_status(False))
            if actual.claim_id != expected.claim_id:
                print(f"    claim_id: actual={actual.claim_id!r} expected={expected.claim_id!r}")
            if actual.entity_refs != expected.entity_refs:
                print(f"    entity_refs: actual={actual.entity_refs} expected={expected.entity_refs}")
            if sorted(actual.supporting_evidence_ids) != sorted(
                expected.supporting_evidence_ids
            ):
                print(
                    "    supporting_evidence_ids: "
                    f"actual={actual.supporting_evidence_ids} "
                    f"expected={expected.supporting_evidence_ids}"
                )
            if sorted(actual.counter_evidence_ids) != sorted(
                expected.counter_evidence_ids
            ):
                print(
                    "    counter_evidence_ids: "
                    f"actual={actual.counter_evidence_ids} "
                    f"expected={expected.counter_evidence_ids}"
                )
        print()

    if all_match:
        print("Overall: MATCH")
    else:
        print("Overall: DIFFERENCE")
    print()
    return all_match


def main(argv: list[str] | None = None) -> int:
    _configure_stdout()
    args = _parse_args(argv or sys.argv[1:])

    graph = _load_graph()
    role = _load_role()

    _print_header(graph, role)

    started = time.perf_counter()
    claims = ClaimSynthesizer().synthesize(graph, MaterialityMap(), role)
    elapsed_ms = (time.perf_counter() - started) * 1000

    if not claims:
        print("No claims produced.")
        _print_timing(elapsed_ms)
        return 0

    for claim in claims:
        _print_claim(claim)

    _print_timing(elapsed_ms)
    _print_summary(claims)

    exit_code = 0

    if args.json:
        _print_json(claims)

    if args.compare:
        expected = _load_expected_reasoning()
        actual_by_id = {claim.claim_id: claim for claim in claims}
        expected_by_id = {claim.claim_id: claim for claim in expected.claims}
        if not _print_compare(actual_by_id, expected_by_id):
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
