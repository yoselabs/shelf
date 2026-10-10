"""Reports: a markdown table per concern (design D18), JSON, and the short gate form."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from blueprint.model import FixedBy, Verdict
from blueprint.profile import STATE_DIR

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path

    from blueprint.runner import Row, Run

_MARK = {Verdict.PASSING: "✅", Verdict.NOT_CHECKED: "🔒", Verdict.NOT_APPLICABLE: "-"}


def mark(row: Row) -> str:
    """One status mark: ✅ passing · ❌ failing · ⚠️ needs the owner · 🔒 could not be checked."""
    if row.verdict in _MARK:
        return _MARK[row.verdict]
    return "⚠️" if row.fixed_by is FixedBy.OWNER else "❌"


def _yn(value: object) -> str:
    return "-" if value is None else ("yes" if value else "no")


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def table(rows: list[Row] | tuple[Row, ...]) -> str:
    """The rows as one markdown table."""
    lines = ["| | checkpoint | set up | working | evidence | remediation | fixed by |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        gap = " (blueprint gap)" if r.blueprint_gap else ""
        by = r.fixed_by if r.remediation else "-"
        lines.append(
            f"| {mark(r)} | `{r.id}`{gap} | {_yn(r.set_up)} | {_yn(r.working)} | "
            f"{_cell(r.evidence)} | {_cell(r.remediation) or '-'} | {by} |"
        )
    return "\n".join(lines)


def _header(run: Run) -> str:
    p = run.profile
    return (
        f"kind: {p.kind} · stacks: {', '.join(p.stacks) or 'none detected'} · surfaces: {', '.join(p.surfaces) or '-'} · "
        f"traits: {', '.join(p.traits) or '-'} · tracker: {p.tracker or 'none'} · checkpoint set: `{run.set_hash}`"
    )


LAYER_TITLES = {"generic": "Generic: any repo", "stack": "Stack-specific", "framework": "Framework-specific", "agent": "Agent harness"}


def _concerns(run: Run) -> list[tuple[str, str]]:
    """`(layer, concern)` in layer order, then first appearance."""
    seen = dict.fromkeys((r.layer, r.concern) for r in run.rows)
    return sorted(seen, key=lambda lc: list(LAYER_TITLES).index(lc[0]) if lc[0] in LAYER_TITLES else len(LAYER_TITLES))


def summary(run: Run) -> str:
    """One row per concern, grouped by layer: the owner's view of a run."""
    lines = ["| layer | concern | ✅ | ❌ | ⚠️ | 🔒 | first to fix |", "|---|---|---|---|---|---|---|"]
    last_layer = ""
    for layer, concern in _concerns(run):
        rows = [r for r in run.rows if r.concern == concern]
        count = {m: sum(mark(r) == m for r in rows) for m in ("✅", "❌", "⚠️", "🔒")}
        first = next((r for r in rows if mark(r) in {"❌", "⚠️"}), None)
        gaps = sum(r.blueprint_gap for r in rows)
        note = f"`{first.id}`: {_cell(first.evidence)[:90]}" if first else ("blueprint gap" if gaps else "-")
        title = LAYER_TITLES.get(layer, layer) if layer != last_layer else ""
        last_layer = layer
        lines.append(f"| {title} | {concern} | {count['✅']} | {count['❌']} | {count['⚠️']} | {count['🔒']} | {note} |")
    return "\n".join(lines)


def markdown(run: Run) -> str:
    """The whole run: the summary, then one table per concern under its layer."""
    out = [_header(run), ""]
    out += [f"⚠️ {p}" for p in run.problems]
    out += [summary(run), ""]
    last_layer = ""
    for layer, concern in _concerns(run):
        if layer != last_layer:
            out += [f"# {LAYER_TITLES.get(layer, layer)}", ""]
            last_layer = layer
        out += [f"## {concern}", "", table([r for r in run.rows if r.concern == concern]), ""]
    return "\n".join(out)


def gate(run: Run) -> str:
    """The `make blueprint` form: one line per checkpoint that is not passing."""
    lines = [f"blueprint: {p}" for p in run.problems]
    lines += [
        f"blueprint: {mark(r)} {r.id} -- {r.verdict}: {r.evidence}" + (f" -> {r.remediation}" if r.remediation else "")
        for r in run.rows
        if r.verdict not in {Verdict.PASSING, Verdict.NOT_APPLICABLE}
    ]
    passed = sum(r.verdict is Verdict.PASSING for r in run.rows)
    lines.append(f"blueprint: {passed}/{len(run.rows)} passing (set {run.set_hash})")
    return "\n".join(lines)


def as_json(run: Run) -> str:
    """The run as JSON, for agents and evals."""
    p = run.profile
    return json.dumps(
        {
            "profile": {"kind": p.kind, "surfaces": p.surfaces, "traits": p.traits, "stacks": p.stacks, "tracker": p.tracker},
            "set_hash": run.set_hash,
            "problems": run.problems,
            "rows": [
                {
                    "id": r.id,
                    "concern": r.concern,
                    "statement": r.statement,
                    "verdict": str(r.verdict),
                    "set_up": r.set_up,
                    "working": r.working,
                    "evidence": r.evidence,
                    "remediation": r.remediation,
                    "fixed_by": str(r.fixed_by),
                    "blueprint_gap": r.blueprint_gap,
                    "layer": r.layer,
                }
                for r in run.rows
            ],
        },
        indent=2,
        ensure_ascii=False,
    )


def write(run: Run, repo: Path, today: date) -> list[Path]:
    """Write `docs/blueprint/README.md` (the summary) and `<concern>.md` per concern; return the paths."""
    out_dir = repo / STATE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = f"Generated by `blueprint check --write` on {today.isoformat()}; do not edit."
    index = out_dir / "README.md"
    index.write_text(f"# Blueprint\n\n{stamp}\n\n{_header(run)}\n\n{summary(run)}\n")
    written = [index]
    for layer, concern in _concerns(run):
        rows = [r for r in run.rows if r.concern == concern]
        path = out_dir / f"{concern.replace('/', '-')}.md"
        path.write_text(f"# Blueprint: {concern} ({LAYER_TITLES.get(layer, layer)})\n\n{stamp}\n\n{_header(run)}\n\n{table(rows)}\n")
        written.append(path)
    return written
