"""Waivers (ADR 0018): the only way a repo waits on a checkpoint the pinned engine judges.

A waiver is `[[tool.blueprint.waivers]]` with `id`, `reason`, `since` and `until` (at most 90 days after `since`, so a
renewal cannot run forever: the first `since` stays in git history), read from
`docs/blueprint/blueprint.toml` and from `pyproject.toml`. This module loads and judges them; the runner applies them.
"""

from __future__ import annotations

import contextlib
import subprocess
import tomllib
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

MAX_DAYS = 90


@dataclass(frozen=True)
class Waiver:
    """One dated, reasoned wait on one checkpoint. `problem` is set when it does not count."""

    id: str
    reason: str
    until: date | None
    problem: str | None = None
    since: date | None = None

    def days_left(self, today: date) -> int:
        """Days from `today` to `until`; 0 on the last day."""
        return ((self.until or today) - today).days


def _one(raw: object, today: date) -> Waiver | None:
    if not isinstance(raw, dict):
        return None
    wid = str(raw.get("id", "")).strip()
    reason = str(raw.get("reason", ""))
    until = _as_date(raw.get("until"))
    since = _as_date(raw.get("since"))
    what = f"waiver {wid!r}"
    problem = None
    if not wid:
        return Waiver("", reason, until, "a waiver has no id", since)
    if not reason.strip():
        problem = f"{what} has no reason"
    elif until is None:
        problem = f"{what} needs `until`, a date (YYYY-MM-DD)"
    elif since is None:
        problem = f"{what} needs `since`, the date it was first granted (YYYY-MM-DD); a renewal keeps the first date"
    elif since > today:
        problem = f"{what} has `since` {since.isoformat()} in the future"
    elif until < today:
        problem = f"{what} expired {until.isoformat()}: it excuses nothing now; fix the checkpoint or renew with a new reason"
    elif until > since + timedelta(days=MAX_DAYS):
        problem = f"{what} runs until {until.isoformat()}, more than {MAX_DAYS} days after since {since.isoformat()}; fix the checkpoint"
    elif until > today + timedelta(days=MAX_DAYS):
        problem = f"{what} runs until {until.isoformat()}, more than {MAX_DAYS} days out; shorten it"
    return Waiver(wid, reason, until, problem, since)


def _as_date(value: object) -> date | None:
    """A TOML date, a datetime (its day) or an ISO string; anything else is None."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and _is_iso(value):
        return date.fromisoformat(value)
    return None


def _is_iso(text: str) -> bool:
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True


def declared(data: dict[str, Any]) -> list[object]:  # Any: parsed TOML, read key by key
    """The raw `[[tool.blueprint.waivers]]` entries of one parsed TOML file."""
    tool = data.get("tool")
    found = tool.get("blueprint") if isinstance(tool, dict) else None
    waivers = found.get("waivers") if isinstance(found, dict) else None
    return list(waivers) if isinstance(waivers, list) else []


def load(repo: Path, blueprint_toml: dict[str, Any], today: date) -> tuple[Waiver, ...]:  # Any: parsed TOML, read key by key
    """Every waiver the repo declares, in `blueprint.toml` and `pyproject.toml`."""
    raw = declared(blueprint_toml)
    # the stack check reports a broken pyproject; waivers there simply do not exist
    with contextlib.suppress(OSError, tomllib.TOMLDecodeError):
        raw += declared(tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8")))
    return tuple(w for r in raw if (w := _one(r, today)) is not None)


def unknown(waivers: Iterable[Waiver], known: set[str]) -> tuple[str, ...]:
    """One problem per waiver naming a checkpoint the pinned engine does not have."""
    return tuple(
        f"waiver {w.id!r} is not a checkpoint of this blueprint version (renamed or removed?); delete it"
        for w in waivers
        if w.id and w.id not in known
    )


READ_FILES = ("blueprint.toml", "docs/blueprint/blueprint.toml", "pyproject.toml")


def stray(repo: Path) -> tuple[str, ...]:
    """One notice per other TOML file that declares waivers: the audit reads only two files, so they count for nothing."""
    try:
        out = subprocess.run(
            ["git", "grep", "--untracked", "-l", "-E", r"^\[\[?tool\.blueprint\.waivers|^waivers *=", "--", "*.toml"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ()
    return tuple(
        f"waivers in {path} are not read: put them in docs/blueprint/blueprint.toml or the root pyproject.toml"
        for path in sorted(out.split())
        if path not in READ_FILES
    )
