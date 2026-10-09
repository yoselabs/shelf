"""Is a recurring job due now? Schedule parsing and the due check.

Two schedule flavours:

- **interval** — ``"30s"``, ``"15m"``, ``"6h"``, ``"1d"`` (a positive integer +
  a unit). Never-run → due immediately; then due once the interval has elapsed.
- **cron** — a standard 5-field expression (``"0 3 * * *"``, ``"*/15 * * * *"``),
  parsed by ``croniter``. Never-run → due at the *next* scheduled fire (no
  backfire on discovery); then due once a scheduled fire has passed since the last
  run.

:func:`schedule_is_due` is the single entry point a scheduler calls; it routes by
flavour and returns ``False`` for an empty or unparsable spec — logged at debug, never
raised, so one bad job file never stops a scheduler's loop.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

from croniter import croniter

log = logging.getLogger(__name__)

_INTERVAL_RE = re.compile(r"^(\d+)([smhd])$")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_interval(spec: str | None) -> timedelta | None:
    """Parse ``"30s"``/``"15m"``/``"6h"``/``"1d"`` into a positive timedelta.

    Returns None for an empty/None spec, an unparsable string, a non-positive
    count, or a cron-like expression (use :func:`is_cron_like` to tell the last
    case apart).
    """
    if not spec:
        return None
    token = spec.strip()
    match = _INTERVAL_RE.match(token)
    if match is None:
        return None
    count = int(match.group(1))
    if count <= 0:
        return None
    return timedelta(seconds=count * _UNIT_SECONDS[match.group(2)])


def is_cron_like(spec: str | None) -> bool:
    """True if ``spec`` looks like a cron expression (spaces or cron glyphs).

    Interval strings are single tokens with no spaces or ``*`` / ``/``, so this
    cleanly separates cron from "just invalid".
    """
    if not spec:
        return False
    token = spec.strip()
    return " " in token or "*" in token or "/" in token


def is_valid_cron(spec: str | None) -> bool:
    """True if ``spec`` is a cron expression ``croniter`` can parse."""
    if not spec:
        return False
    return croniter.is_valid(spec.strip())


def is_due(interval: timedelta, last_run_at: datetime | None, now: datetime) -> bool:
    """An interval job is due if never run, or its interval has elapsed since last run."""
    if last_run_at is None:
        return True
    return now - last_run_at >= interval


def cron_is_due(spec: str, last_run_at: datetime | None, now: datetime) -> bool:
    """A cron job is due when a scheduled fire has occurred at/before ``now``.

    Basis is the last run, or ``now`` when never run — so a freshly discovered cron
    job fires at its *next* scheduled time rather than backfiring for every past
    occurrence. ``croniter(spec, base).get_next()`` is the first fire strictly after
    ``base``; the job is due once that fire is at/before ``now``. An unparsable
    expression is never due (logged, not raised).
    """
    base = last_run_at or now
    try:
        next_fire = croniter(spec.strip(), base).get_next(datetime)
    except (ValueError, KeyError):
        log.debug("job schedule %r is not a valid cron expression; skipping", spec)
        return False
    return next_fire <= now


def schedule_is_due(spec: str | None, last_run_at: datetime | None, now: datetime) -> bool:
    """Single due-check a scheduler calls; routes interval vs cron vs invalid.

    ``None``/empty (no schedule) and unparsable specs are never due.
    """
    if not spec:
        return False
    interval = parse_interval(spec)
    if interval is not None:
        return is_due(interval, last_run_at, now)
    if is_cron_like(spec):
        return cron_is_due(spec, last_run_at, now)
    log.debug("job schedule %r is neither a valid interval nor cron; skipping", spec)
    return False


__all__ = [
    "cron_is_due",
    "is_cron_like",
    "is_due",
    "is_valid_cron",
    "parse_interval",
    "schedule_is_due",
]
