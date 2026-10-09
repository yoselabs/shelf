"""A time value as the half-open interval it names.

``2026`` is the whole year, ``2026-07`` the whole month, ``2026-07-09`` the day, and an
instant its one second. Storing every time as ``[lo, hi)`` lets one comparison serve every
precision: equality is overlap, so a query for ``2026-07`` finds a day in July and a
month-precision ``2026-07`` alike, and a range compares interval starts.

The bounds are **naive UTC**. A tz-aware value bound into a database can be shifted through
the session time zone (``10:00Z`` read back as ``13:00``), so nothing tz-aware leaves here.

:func:`format_interval` is the inverse for display: the precision is the width.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta

_PARTIAL = re.compile(r"^(?P<y>\d{4})(?:-(?P<m>\d{2})(?:-(?P<d>\d{2}))?)?$")
_INSTANT = timedelta(seconds=1)
_DAY = timedelta(days=1)
_MONTH_MAX = timedelta(days=31)
_INSTANT_MIN_LEN = 11  # anything shorter than `YYYY-MM-DDT` is not an instant


def _utc(value: datetime) -> datetime:
    """``value`` in UTC without a zone; a naive value is taken to be UTC already."""
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value.replace(microsecond=0)


def _month_after(year: int, month: int) -> datetime:
    return datetime(year + (month == 12), month % 12 + 1, 1)  # noqa: DTZ001 — naive UTC by design


def _partial(text: str) -> tuple[datetime, datetime] | None:
    m = _PARTIAL.match(text)
    if m is None:
        return None
    year = int(m["y"])
    try:
        if m["d"]:
            lo = datetime(year, int(m["m"]), int(m["d"]))  # noqa: DTZ001
            return lo, lo + _DAY
        if m["m"]:
            month = int(m["m"])
            return datetime(year, month, 1), _month_after(year, month)  # noqa: DTZ001
    except ValueError:  # month 13, day 32
        return None
    return datetime(year, 1, 1), datetime(year + 1, 1, 1)  # noqa: DTZ001


def _instant(text: str) -> tuple[datetime, datetime] | None:
    if len(text) < _INSTANT_MIN_LEN:
        return None
    try:
        lo = _utc(datetime.fromisoformat(text))  # 3.11+ reads a trailing `Z`
    except ValueError:
        return None
    return lo, lo + _INSTANT


def interval(value: object) -> tuple[datetime, datetime] | None:
    """The ``[lo, hi)`` span ``value`` names, or ``None`` when it is not a time.

    Accepts ``date``, ``datetime`` and text: ``YYYY``, ``YYYY-MM``, ``YYYY-MM-DD``, or an
    ISO instant with or without a zone. A ``bool`` is an ``int`` in Python and is refused
    like one.
    """
    if isinstance(value, datetime):
        lo = _utc(value)
        return lo, lo + _INSTANT
    if isinstance(value, date):
        lo = datetime(value.year, value.month, value.day)  # noqa: DTZ001
        return lo, lo + _DAY
    if not isinstance(value, str):
        return None
    text = value.strip()
    return _partial(text) or _instant(text)


def format_interval(lo: datetime, hi: datetime) -> str:
    """``lo`` written at the precision the span's width says: instant, day, month, year."""
    width = hi - lo
    if width <= _INSTANT:
        return lo.strftime("%Y-%m-%dT%H:%M:%SZ")
    if width <= _DAY:
        return lo.strftime("%Y-%m-%d")
    if width <= _MONTH_MAX:
        return lo.strftime("%Y-%m")
    return lo.strftime("%Y")


__all__ = ["format_interval", "interval"]
