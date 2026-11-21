"""The debt report: every row whose reason starts with `debt:`, grouped by rule."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from any_arch.rule import Rule


def debt(*rules: Rule) -> dict[str, dict[str, str]]:
    """rule name -> {key: reason} for the rule's `debt:` rows; a rule with no debt is left out."""
    report = {rule.name: {key: row.reason for key, row in sorted(rule.rows.items()) if row.reason.startswith("debt:")} for rule in rules}
    return {name: owed for name, owed in report.items() if owed}


def debt_text(*rules: Rule) -> str:
    """The report as lines: a rule header with its row count, then one `key: reason` line per row."""
    lines: list[str] = []
    for name, owed in debt(*rules).items():
        lines.append(f"{name} ({len(owed)})")
        lines.extend(f"  {key}: {reason.removeprefix('debt:').strip()}" for key, reason in owed.items())
    return "\n".join(lines)
