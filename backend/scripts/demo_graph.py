"""Demo: run sample multi-source evidence through the Graph Intelligence Layer.

    python scripts/demo_graph.py            # human-readable report
    python scripts/demo_graph.py --json     # full GraphReport as JSON
    python scripts/demo_graph.py --graph    # full CandidateGraph as JSON

It builds a candidate from resume + GitHub + LinkedIn + certification evidence and
prints what the layer produces: skills with *fused* confidence (green/yellow/red),
the evidence proving each, duplicate entities it merged, and capabilities it
*inferred* beyond the explicit claims (e.g. Backend Development from FastAPI +
Python). No server or database required.
"""

from __future__ import annotations

import argparse
import json

from app.intelligence.candidate_graph import GraphBuilder, build_report
from app.intelligence.candidate_graph.report import GraphReport
from app.shared.enums import EvidenceSource, EvidenceType
from app.shared.models.evidence import Evidence

# ANSI colours for the confidence bands (degrade gracefully if piped).
_BAND = {"green": "\033[92m", "yellow": "\033[93m", "red": "\033[91m"}
_RESET = "\033[0m"


def sample_evidence() -> list[Evidence]:
    """A realistic candidate: Python attested 3 ways, a duplicate DB spelling, a
    FastAPI repo (drives backend-capability inference), and an AWS certification."""
    c = "cand_demo"

    def ev(i, source, etype, ref, claim, conf, prov=None):
        return Evidence(
            evidence_id=f"ev_{i:03d}", candidate_id=c, source=source,
            evidence_type=etype, entity_ref=ref, claim=claim, confidence=conf,
            provenance=prov or {},
        )

    return [
        # Python — three independent sources => strong fused confidence.
        ev(1, EvidenceSource.RESUME, EvidenceType.SKILL, "Python", "Lists Python on resume", 0.60),
        ev(2, EvidenceSource.GITHUB, EvidenceType.SKILL, "Python", "12k LOC of Python across repos", 0.90),
        ev(3, EvidenceSource.LINKEDIN, EvidenceType.SKILL, "Python", "Endorsed for Python", 0.70),
        # A GitHub repo whose languages/topics drive inference (USES + PROVES + DOMAIN).
        ev(4, EvidenceSource.GITHUB, EvidenceType.REPOSITORY, "ClinicBot",
           "Owns repo ClinicBot (214 commits)", 0.92,
           {"repository": "ClinicBot", "commits": 214,
            "languages": ["Python", "FastAPI"], "topics": ["PostgreSQL", "Docker"]}),
        # Duplicate database spellings => dedup should collapse to one node.
        ev(5, EvidenceSource.RESUME, EvidenceType.TOOL, "Postgres", "Used Postgres", 0.60),
        ev(6, EvidenceSource.GITHUB, EvidenceType.TOOL, "PostgreSQL", "Postgres in repo stack", 0.85),
        # Single-source skill => yellow band.
        ev(7, EvidenceSource.RESUME, EvidenceType.SKILL, "JavaScript", "Resume mentions JS", 0.55),
        # Experience + certification.
        ev(8, EvidenceSource.LINKEDIN, EvidenceType.EXPERIENCE, "aws",
           "ML Engineer Intern at AWS", 0.75),
        ev(9, EvidenceSource.MANUAL, EvidenceType.CERTIFICATION, "AWS Certified Python Developer",
           "Holds AWS Python certification", 0.95, {"subject": "Python"}),
    ]


def render(report: GraphReport) -> None:
    print(f"\n{'='*70}\nCANDIDATE INTELLIGENCE REPORT  —  {report.candidate_id}")
    print(f"graph_id={report.graph_id}")
    print(f"nodes={report.node_count}  edges={report.edge_count}  "
          f"evidence={report.evidence_count}\n{'='*70}")

    print("\nSKILLS PORTFOLIO  (fused confidence across sources)")
    print(f"  {'skill':<22}{'conf':>6}  {'band':<8}{'proofs':>7}  sources")
    for s in report.skills_portfolio:
        col = _BAND.get(s.level.value, "")
        tag = " [inferred]" if s.inferred else ""
        print(f"  {s.name:<22}{s.confidence:>6.2f}  "
              f"{col}{s.level.value.upper():<8}{_RESET}{s.proven_by:>5}    "
              f"{', '.join(s.sources) or '—'}{tag}")

    print("\nINFERRED CAPABILITIES  (beyond explicit claims)")
    if not report.inferred_capabilities:
        print("  (none)")
    for c in report.inferred_capabilities:
        col = _BAND.get(c.level.value, "")
        print(f"  {col}●{_RESET} {c.name:<24}{c.confidence:>5.2f}   "
              f"derived from: {', '.join(c.derived_from) or '—'}")

    print("\nPROJECTS / REPOSITORIES")
    for p in report.projects:
        print(f"  {p.name:<22}{p.confidence:>5.2f}   tech: {', '.join(p.technologies) or '—'}")

    print("\nEXPERIENCE")
    for e in report.experience:
        dom = f"  ({e.domain})" if e.domain else ""
        print(f"  {e.organization:<22}{e.confidence:>5.2f}{dom}")

    cs = report.confidence_summary
    print(f"\nCONFIDENCE SUMMARY  "
          f"{_BAND['green']}green={cs.get('green',0)}{_RESET}  "
          f"{_BAND['yellow']}yellow={cs.get('yellow',0)}{_RESET}  "
          f"{_BAND['red']}red={cs.get('red',0)}{_RESET}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print the GraphReport as JSON")
    parser.add_argument("--graph", action="store_true", help="print the full CandidateGraph as JSON")
    args = parser.parse_args()

    graph = GraphBuilder().build("cand_demo", sample_evidence())
    if args.graph:
        print(json.dumps(graph.model_dump(mode="json"), indent=2))
        return
    report = build_report(graph)
    if args.json:
        print(json.dumps(report.model_dump(mode="json"), indent=2))
        return
    render(report)


if __name__ == "__main__":
    main()
