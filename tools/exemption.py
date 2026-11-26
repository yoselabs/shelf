"""One shape for an exemption in a tools allowlist: a reason, and optionally the last day it holds.

An entry is a bare string (the reason, no deadline: the exemption is permanent by nature) or a table
`{ reason = "...", until = 2026-12-27 }`. The day after `until` the entry covers nothing and the check names it. Stdlib only;
the tools that use it run as `python3 -I tools/<name>.py`, which keeps this folder off `sys.path`, so they add it themselves.
"""

from __future__ import annotations

from datetime import date


def reason_of(entry: object) -> str:
    """The reason an entry gives, or an empty string when it has none."""
    text = entry.get("reason") if isinstance(entry, dict) else entry
    return text if isinstance(text, str) else ""


def until_of(entry: object) -> date | None:
    """The last day the entry holds, or None for a permanent one."""
    until = entry.get("until") if isinstance(entry, dict) else None
    return until if isinstance(until, date) else None


def lapsed(entry: object, today: date) -> str | None:
    """`ran out on <date>` when `today` is past the entry's `until`, else None."""
    until = until_of(entry)
    return f"ran out on {until}" if until is not None and today > until else None
