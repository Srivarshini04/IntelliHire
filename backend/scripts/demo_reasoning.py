"""Local demo — full DELULU v2 reasoning + decision pipeline (PR demonstration only).

Loads mock fixtures, runs ReasoningEngine and DecisionEngine, prints a recruiter report.
Not production code. No FastAPI, database, or runtime dependencies.

Usage (from backend/):

    py scripts/demo_reasoning.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.mock import load_graph, load_role_dna
from app.intelligence.decision.decision_engine import DecisionEngine, DecisionResult, Recommendation
from app.intelligence.reasoning.gap_analyzer import GapItem
from app.intelligence.reasoning.reasoning_engine import ReasoningEngine, ReasoningResult
from app.intelligence.reasoning.summary_composer import _CLAIM_LABELS, _pretty_name, _truncate
from app.intelligence.reasoning.uncertainty_detector import UncertaintyItem
from app.shared.models import ReasoningClaim

_WIDTH = 72
_MAX_LINE = 80
_MAX_RATIONALE = 5
_CHECK = "\u2714"
_CROSS = "\u2716"
_WARN = "\u26a0"
_BULLET = "\u2022"
_ENTITY_RE = re.compile(r"\b(?:skill|activity|domain|repo):[a-z0-9_]+\b")


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


def _use_rich() -> bool:
    try:
        import rich  # noqa: F401

        return True
    except ImportError:
        return False


def _pct(value: float) -> str:
    return f"{round(value * 100, 2):.2f}%"


def _confidence_level(overall: float) -> str:
    if overall >= 0.75:
        return "HIGH"
    if overall >= 0.55:
        return "MODERATE"
    return "LOW"


def _confidence_level_emoji(overall: float) -> str:
    if overall >= 0.75:
        return "\U0001f7e2 High"
    if overall >= 0.55:
        return "\U0001f7e1 Moderate"
    return "\U0001f534 Low"


def _format_recommendation(recommendation: Recommendation) -> str:
    return recommendation.value.replace("_", " ").upper()


def _humanize_text(text: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        return _pretty_name(match.group(0))

    return _ENTITY_RE.sub(_replace, text)


def _claim_title(claim: ReasoningClaim) -> str:
    if claim.claim_id in _CLAIM_LABELS:
        return _CLAIM_LABELS[claim.claim_id]
    if claim.entity_refs:
        return _pretty_name(claim.entity_refs[0])
    return _truncate(claim.statement.strip() or claim.conclusion.strip())


def _claim_subtitle(claim: ReasoningClaim) -> str:
    text = (claim.conclusion or claim.statement).strip()
    title = _claim_title(claim)
    if not text or text.lower() == title.lower():
        return ""
    return _truncate(_humanize_text(text))


def _claim_symbol(claim: ReasoningClaim) -> str:
    if claim.supporting_evidence_ids and not (
        claim.counter_evidence_ids
        and len(claim.counter_evidence_ids) >= len(claim.supporting_evidence_ids)
    ):
        return _CHECK
    if claim.counter_evidence_ids:
        return _WARN
    return _BULLET


def _gap_label(item: GapItem) -> str:
    for ref in item.missing_evidence:
        if ":" in ref and not ref.startswith(("supporting_", "corroboration")):
            return _pretty_name(ref)
    return _pretty_name(item.title)


def _gap_detail(item: GapItem) -> str:
    label = _gap_label(item)
    if item.severity == "critical":
        lowered = item.rationale.lower()
        if "no substantiating" in lowered or "no supporting" in lowered:
            return f"Missing production {label} experience"
        return f"{label} experience missing"
    if item.rationale.strip():
        text = _truncate(_humanize_text(item.rationale))
        if label.lower() in text.lower():
            return text
        return f"{label}: {text}"
    return f"{label} exposure limited"


def _uncertainty_detail(item: UncertaintyItem) -> str:
    label = _pretty_name(item.title)
    if item.rationale.strip():
        text = _truncate(_humanize_text(item.rationale))
        if label.lower() in text.lower():
            return text
        return f"{label}: {text}"
    return label


def _extract_entity_key(text: str) -> str | None:
    match = _ENTITY_RE.search(text)
    return match.group(0) if match else None


def _friendly_blocker(text: str) -> str:
    entity = _extract_entity_key(text)
    lowered = text.lower()
    if entity:
        name = _pretty_name(entity)
        if "no supporting evidence" in lowered or "no substantiating" in lowered:
            return f"Missing production {name} experience"
        if "must have" in lowered or "critical" in lowered:
            return f"Required {name} competency not evidenced"
    return _truncate(_humanize_text(text))


def _dedupe_blockers(blockers: list[str]) -> list[str]:
    by_entity: dict[str, list[str]] = {}
    unkeyed: list[str] = []
    for blocker in blockers:
        key = _extract_entity_key(blocker)
        if key:
            by_entity.setdefault(key, []).append(blocker)
        else:
            unkeyed.append(_friendly_blocker(blocker))

    merged: list[str] = []
    for entity in sorted(by_entity):
        texts = by_entity[entity]
        merged.append(_friendly_blocker(texts[0]))

    seen: set[str] = set()
    out: list[str] = []
    for line in merged + unkeyed:
        key = line.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(line)
    return out[:5]


def _short_rationale(lines: list[str]) -> list[str]:
    short: list[str] = []
    for line in lines:
        text = _truncate(_humanize_text(line))
        if not text:
            continue
        if len(text) > 50 and "." in text:
            text = text.split(".", 1)[0].strip()
        short.append(text)
        if len(short) >= _MAX_RATIONALE:
            break
    return short


def _confidence_reason(conf: object) -> str:
    explanation = getattr(conf, "explanation", "").strip()
    if not explanation:
        return "No additional confidence notes."
    parts = re.split(r"[.;]\s+", explanation)
    lines = [_truncate(part.strip(), _MAX_LINE) for part in parts if part.strip()]
    return "\n".join(lines[:3])


def _decision_reason_lines(decision: DecisionResult, reasoning: ReasoningResult) -> list[str]:
    lines: list[str] = []
    supported = sum(1 for c in reasoning.claims if c.supporting_evidence_ids)
    if supported >= 2:
        lines.append("Strong technical profile across multiple competencies")
    if reasoning.gaps.critical:
        lines.append("One or more critical competency gaps")
    elif reasoning.gaps.moderate:
        lines.append("Moderate gaps remain in secondary competencies")
    level = _confidence_level(reasoning.confidence.overall_confidence).title()
    lines.append(f"{level} confidence")
    if reasoning.uncertainties.high:
        lines.append("High-severity uncertainty signals present")
    return _short_rationale(lines)[:_MAX_RATIONALE]


def _next_step_text(decision: DecisionResult) -> str:
    mapping = {
        Recommendation.INTERVIEW_WITH_REVIEW: (
            "Recruiter review recommended before scheduling technical interview."
        ),
        Recommendation.INTERVIEW: "Schedule technical interview.",
        Recommendation.HIRE: "Proceed to technical interview.",
        Recommendation.STRONG_HIRE: "Proceed to final interview.",
        Recommendation.NEEDS_MORE_INFORMATION: "Collect additional evidence before proceeding.",
        Recommendation.REJECT: "Do not proceed with this candidate.",
    }
    return mapping.get(decision.recommendation, decision.next_step)


def print_header_plain(graph_id: str, candidate_id: str, job_id: str) -> None:
    print("=" * _WIDTH)
    print("DELULU AI HIRING REPORT".center(_WIDTH))
    print("=" * _WIDTH)
    print()
    print("Candidate")
    print("-" * 9)
    print(f"Candidate ID : {candidate_id}")
    print(f"Graph ID     : {graph_id}")
    print()
    print("Job")
    print("-" * 3)
    print(f"Job ID       : {job_id}")
    print()


def print_section(title: str) -> None:
    print()
    print("=" * _WIDTH)
    print(title)
    print("=" * _WIDTH)
    print()


def print_claims(claims: list[ReasoningClaim]) -> None:
    print_section("CLAIMS")
    if not claims:
        print("None")
        return
    for claim in claims:
        symbol = _claim_symbol(claim)
        title = _claim_title(claim)
        subtitle = _claim_subtitle(claim)
        print(f"{symbol} {title}")
        if subtitle:
            print(f"  {_truncate(subtitle)}")


def print_gaps(reasoning: ReasoningResult) -> None:
    sections = (
        ("CRITICAL GAPS", reasoning.gaps.critical, _CROSS),
        ("MODERATE GAPS", reasoning.gaps.moderate, _BULLET),
        ("MINOR GAPS", reasoning.gaps.minor, _BULLET),
    )
    for title, items, symbol in sections:
        print_section(title)
        if not items:
            print("None")
            continue
        for item in items:
            print(f"{symbol} {_gap_detail(item)}")


def print_uncertainties(reasoning: ReasoningResult) -> None:
    print_section("UNCERTAINTIES")
    groups = (
        ("HIGH", reasoning.uncertainties.high, _WARN),
        ("MEDIUM", reasoning.uncertainties.medium, _BULLET),
        ("LOW", reasoning.uncertainties.low, _BULLET),
    )
    any_items = False
    for label, items, symbol in groups:
        print(label)
        print()
        if not items:
            print("None")
            print()
            continue
        any_items = True
        for item in items:
            print(f"{symbol} {_uncertainty_detail(item)}")
        print()
    if not any_items:
        print("None")


def print_confidence(reasoning: ReasoningResult) -> None:
    conf = reasoning.confidence
    print_section("CONFIDENCE")
    print("Overall")
    print()
    print(_pct(conf.overall_confidence))
    print()
    print("Level")
    print()
    print(_confidence_level_emoji(conf.overall_confidence))
    print()
    print("Reason")
    print()
    print(_confidence_reason(conf))
    print()
    print("Details")
    print()
    print(f"Claim confidence    : {_pct(conf.claim_confidence)}")
    print(f"Evidence confidence : {_pct(conf.evidence_confidence)}")
    print(f"Uncertainty penalty : {_pct(conf.uncertainty_penalty)}")


def print_summary(reasoning: ReasoningResult) -> None:
    print_section("SUMMARY")
    text = reasoning.summary.overall_summary.strip()
    print(text if text else "None")


def print_decision(decision: DecisionResult, reasoning: ReasoningResult) -> None:
    print_section("HIRING DECISION")
    print("Recommendation")
    print()
    print(_format_recommendation(decision.recommendation))
    print()
    print("Reason")
    print()
    for line in _decision_reason_lines(decision, reasoning):
        print(f"{_BULLET} {line}")
    print()
    print("Next Step")
    print()
    print(_next_step_text(decision))
    print()
    print_section("RATIONALE")
    rationale = _short_rationale(decision.rationale)
    if not rationale:
        print("None")
    else:
        for line in rationale:
            print(f"{_CHECK} {line}")
    print()
    print_section("BLOCKERS")
    blockers = _dedupe_blockers(decision.blockers)
    if not blockers:
        print("None")
    else:
        for blocker in blockers:
            print(f"{_BULLET} {blocker}")


def print_footer() -> None:
    print()
    print("=" * _WIDTH)
    print("END OF REPORT".center(_WIDTH))
    print("=" * _WIDTH)


def _render_rich(reasoning: ReasoningResult, decision: DecisionResult, graph, role) -> None:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    console = Console()

    console.print()
    console.print(Panel.fit("DELULU AI HIRING REPORT", style="bold cyan", padding=(1, 4)))

    meta = Table.grid(padding=(0, 2))
    meta.add_row("Candidate ID", graph.candidate_id)
    meta.add_row("Graph ID", graph.graph_id)
    meta.add_row("Job ID", role.job_id)
    meta.add_row("Role DNA", role.role_dna_id)
    console.print(Panel(meta, title="Candidate", border_style="blue", padding=(1, 2)))
    console.print()

    claims_table = Table(title="Claims", show_header=True, header_style="bold green", border_style="green")
    claims_table.add_column("Status", width=4, justify="center")
    claims_table.add_column("Competency", style="bold")
    claims_table.add_column("Detail", style="dim")
    if reasoning.claims:
        for claim in reasoning.claims:
            symbol = _claim_symbol(claim)
            title = _claim_title(claim)
            subtitle = _claim_subtitle(claim)
            style = "green" if symbol == _CHECK else ("yellow" if symbol == _WARN else "white")
            claims_table.add_row(
                Text(symbol, style=style),
                Text(title, style=style),
                subtitle or "",
            )
    else:
        claims_table.add_row("-", "None", "")
    console.print(claims_table)
    console.print()

    for title, items, symbol in (
        ("Critical Gaps", reasoning.gaps.critical, _CROSS),
        ("Moderate Gaps", reasoning.gaps.moderate, _BULLET),
        ("Minor Gaps", reasoning.gaps.minor, _BULLET),
    ):
        table = Table(
            title=title,
            show_header=False,
            border_style="red" if "Critical" in title else "yellow",
            padding=(0, 1),
        )
        if items:
            for item in items:
                table.add_row(f"{symbol} {_gap_detail(item)}")
        else:
            table.add_row("None")
        console.print(table)
        console.print()

    unc_table = Table(title="Uncertainties", border_style="magenta", padding=(0, 1))
    unc_table.add_column("Severity", style="bold", width=10)
    unc_table.add_column("Detail")
    rows = (
        [(f"HIGH {_WARN}", _uncertainty_detail(item)) for item in reasoning.uncertainties.high]
        + [("MEDIUM", _uncertainty_detail(item)) for item in reasoning.uncertainties.medium]
        + [("LOW", _uncertainty_detail(item)) for item in reasoning.uncertainties.low]
    )
    if rows:
        for severity, detail in rows:
            unc_table.add_row(severity, detail)
    else:
        unc_table.add_row("-", "None")
    console.print(unc_table)
    console.print()

    conf = reasoning.confidence
    conf_panel = Table.grid(padding=(0, 2))
    conf_panel.add_row("Overall", Text(_pct(conf.overall_confidence), style="bold cyan"))
    conf_panel.add_row("Level", _confidence_level_emoji(conf.overall_confidence))
    conf_panel.add_row("Claim", _pct(conf.claim_confidence))
    conf_panel.add_row("Evidence", _pct(conf.evidence_confidence))
    conf_panel.add_row("Penalty", _pct(conf.uncertainty_penalty))
    console.print(
        Panel(
            conf_panel,
            title="Confidence",
            subtitle=Text(_confidence_reason(conf), style="dim"),
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()

    console.print(
        Panel(
            reasoning.summary.overall_summary or "None",
            title="Summary",
            border_style="white",
            padding=(1, 2),
        )
    )
    console.print()

    reason_lines = _decision_reason_lines(decision, reasoning)
    decision_body = Table.grid(padding=(0, 1))
    decision_body.add_row(
        Text("Recommendation", style="bold"),
        Text(_format_recommendation(decision.recommendation), style="bold green"),
    )
    decision_body.add_row(Text("Score", style="bold"), f"{decision.score:.2f}")
    decision_body.add_row(Text("Reason", style="bold"), "")
    for line in reason_lines:
        decision_body.add_row("", f"{_BULLET} {line}")
    decision_body.add_row(Text("Next Step", style="bold"), _next_step_text(decision))
    console.print(Panel(decision_body, title="Hiring Decision", border_style="bold green", padding=(1, 2)))
    console.print()

    rationale_text = "\n".join(f"{_CHECK} {line}" for line in _short_rationale(decision.rationale)) or "None"
    blockers_text = (
        "\n".join(f"{_BULLET} {line}" for line in _dedupe_blockers(decision.blockers)) or "None"
    )
    console.print(Panel(rationale_text, title="Rationale", border_style="blue", padding=(1, 2)))
    console.print(Panel(blockers_text, title="Blockers", border_style="red", padding=(1, 2)))
    console.print()
    console.print(Panel.fit("END OF REPORT", style="bold", padding=(0, 4)))


def _render_plain(reasoning: ReasoningResult, decision: DecisionResult, graph, role) -> None:
    print_header_plain(graph.graph_id, graph.candidate_id, role.job_id)
    print_claims(reasoning.claims)
    print_gaps(reasoning)
    print_uncertainties(reasoning)
    print_confidence(reasoning)
    print_summary(reasoning)
    print_decision(decision, reasoning)
    print_footer()


def main() -> int:
    _configure_stdout()

    graph = load_graph()
    role = load_role_dna()

    reasoning = ReasoningEngine().reason(graph, role)
    decision = DecisionEngine().decide(reasoning)

    if _use_rich():
        _render_rich(reasoning, decision, graph, role)
    else:
        _render_plain(reasoning, decision, graph, role)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
