"""A Rule finds hits in parsed files; its rows are the reasoned list of hits that are allowed to stay."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from any_arch.source import sources

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping
    from pathlib import Path

    from any_arch.source import Source

Hit = tuple[str, int]  # (key, line): the row key the hit belongs to, and where it is


@dataclass(frozen=True)
class Row:
    """One allowed key. `count` is the exact number of hits the key may have; None means any number of at least one.

    `until` is the last day the row covers its key; the day after, `check` fails it. A `debt:` row must have one, its
    own or its rule's `debt_until`: owed work has a deadline, or it is not owed, it is kept (`outcome:`).
    """

    reason: str
    count: int | None = None
    until: date | None = None


@dataclass(frozen=True)
class Rule:
    """`find` yields the hits of one file; `rows` maps key -> Row; `fix` is the text a failure shows.

    `kinds` are the reason prefixes a row may use (`debt`, `outcome`, ...); empty means any non-blank reason.
    `scope` are the globs, relative to the repo root, of the files `find` sees.
    `debt_until` is the deadline of every `debt:` row that has no `until` of its own.
    """

    name: str
    fix: str
    find: Callable[[Source], Iterable[Hit]]
    rows: Mapping[str, Row]
    kinds: tuple[str, ...] = ()
    scope: tuple[str, ...] = ("packages/*/src/**/*.py",)
    debt_until: date | None = None


def rows(reason: str, *keys: str | tuple[str, int], until: date | None = None) -> dict[str, Row]:
    """One reason (and one `until`) shared by many keys; a `(key, count)` pair makes that key an exact-count row."""
    return {k if isinstance(k, str) else k[0]: Row(reason, None if isinstance(k, str) else k[1], until) for k in keys}


def findings(rule: Rule, root: Path) -> dict[str, list[int]]:
    """key -> the lines of its hits, over `root`."""
    found: dict[str, list[int]] = {}
    for source in sources(root, rule.scope):
        for key, line in rule.find(source):
            found.setdefault(key, []).append(line)
    return {key: sorted(lines) for key, lines in found.items()}


def _bad_reason(reason: str, kinds: tuple[str, ...]) -> bool:
    if not reason.strip():
        return True
    return bool(kinds) and not reason.startswith(tuple(f"{kind}: " for kind in kinds))


def _deadline_problem(key: str, row: Row, rule: Rule, today: date) -> str | None:
    until = row.until or (rule.debt_until if row.reason.startswith("debt:") else None)
    if until is None and row.reason.startswith("debt:"):
        return f"undated: {key} is debt with no `until`; give the row (or the rule's `debt_until`) a date, or make it `outcome:`"
    if until is not None and today > until:
        return f"expired: {key} was covered until {until}; fix the hit, or renew the row with a new date and the reason it still stands"
    return None


def check(rule: Rule, root: Path, today: date | None = None) -> None:
    """Fail, with the rule's fix text, on a hit beyond its row, a row with no hit, a wrong count, a bad reason, or a late debt row.

    `today` is the clock, injected for tests; it defaults to the real date.
    """
    today = today or date.today()  # noqa: DTZ011 -- the deadline is a calendar day on the owner's machine, no timezone
    found = findings(rule, root)
    problems: list[str] = []
    for key, lines in found.items():
        row = rule.rows.get(key)
        if row is None:
            problems.append(f"new: {key} at lines {lines}")
        elif row.count is not None and len(lines) > row.count:
            problems.append(f"over: {key} has {len(lines)} hits, its row allows {row.count}")
    for key, row in rule.rows.items():
        hits = len(found.get(key, ()))
        if hits == 0:
            problems.append(f"stale: {key} has no hit; delete its row")
        elif row.count is not None and hits < row.count:
            problems.append(f"stale: {key} has {hits} hits, its row says {row.count}")
        if (late := _deadline_problem(key, row, rule, today)) is not None:
            problems.append(late)
        if _bad_reason(row.reason, rule.kinds):
            problems.append(f"reason: {key} needs a non-blank reason starting with one of {list(rule.kinds) or 'any text'}")
    if problems:
        raise AssertionError(f"{rule.name}: {rule.fix}\n" + "\n".join(problems))


def plant(rule: Rule, tmp_path: Path, source: str, path: str = "packages/pkg/src/pkg/mod.py") -> dict[str, list[int]]:
    """Write `source` at `path` under `tmp_path` and return what `rule` finds there: the planted-violation test."""
    module = tmp_path / path
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text(source, encoding="utf-8")
    return findings(rule, tmp_path)
