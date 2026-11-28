"""Waivers (ADR 0018): the only way a repo waits on a checkpoint the pinned engine judges.

A waiver is `[[tool.blueprint.waivers]]` with `id`, `reason` and `until` (at most 90 days out), read from
`docs/blueprint/blueprint.toml` and from `pyproject.toml`. This module loads and judges them; the runner applies them.
"""

from __future__ import annotations

import contextlib
import tomllib
from dataclasses import dataclass
from datetime import date, timedelta
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

    def days_left(self, today: date) -> int:
        """Days from `today` to `until`; 0 on the last day."""
        return ((self.until or today) - today).days


def _one(raw: object, today: date) -> Waiver | None:
    if not isinstance(raw, dict):
        return None
    wid = str(raw.get("id", "")).strip()
    reason = str(raw.get("reason", ""))
    until = raw.get("until")
    until = date.fromisoformat(until) if isinstance(until, str) and _is_iso(until) else until
    until = until if isinstance(until, date) else None
    what = f"waiver {wid!r}"
    problem = None
    if not wid:
        return Waiver("", reason, until, "a waiver has no id")
    if not reason.strip():
        problem = f"{what} has no reason"
    elif until is None:
        problem = f"{what} needs `until`, a date (YYYY-MM-DD)"
    elif until < today:
        problem = f"{what} expired {until.isoformat()}: it excuses nothing now; fix the checkpoint or renew with a new reason"
    elif until > today + timedelta(days=MAX_DAYS):
        problem = f"{what} runs until {until.isoformat()}, more than {MAX_DAYS} days out; shorten it"
    return Waiver(wid, reason, until, problem)


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
