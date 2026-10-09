"""A time value is the half-open interval it names (moved from a2kay tests/core/test_time_interval.py)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from partial_time import format_interval, interval


def _dt(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second)  # noqa: DTZ001 — naive UTC on purpose


@pytest.mark.parametrize(
    ("value", "lo", "hi"),
    [
        ("2026", _dt(2026, 1, 1), _dt(2027, 1, 1)),
        ("2026-07", _dt(2026, 7, 1), _dt(2026, 8, 1)),
        ("2026-12", _dt(2026, 12, 1), _dt(2027, 1, 1)),
        ("2026-07-09", _dt(2026, 7, 9), _dt(2026, 7, 10)),
        ("2026-07-09T10:00:00Z", _dt(2026, 7, 9, 10), _dt(2026, 7, 9, 10, 0, 1)),
        ("2026-07-09T13:00:00+03:00", _dt(2026, 7, 9, 10), _dt(2026, 7, 9, 10, 0, 1)),
        ("2026-07-09 10:00", _dt(2026, 7, 9, 10), _dt(2026, 7, 9, 10, 0, 1)),
        (" 2026-07 ", _dt(2026, 7, 1), _dt(2026, 8, 1)),
        (date(2026, 7, 9), _dt(2026, 7, 9), _dt(2026, 7, 10)),
        (datetime(2026, 7, 9, 10, tzinfo=UTC), _dt(2026, 7, 9, 10), _dt(2026, 7, 9, 10, 0, 1)),
        (datetime(2026, 7, 9, 13, tzinfo=timezone(timedelta(hours=3))), _dt(2026, 7, 9, 10), _dt(2026, 7, 9, 10, 0, 1)),
        (datetime(2026, 7, 9, 10, 0, 0, 999_999, tzinfo=UTC), _dt(2026, 7, 9, 10), _dt(2026, 7, 9, 10, 0, 1)),
    ],
)
def test_a_value_is_the_span_it_names(value: object, lo: datetime, hi: datetime) -> None:
    assert interval(value) == (lo, hi)


def test_bounds_are_naive_utc() -> None:
    """A database compares a tz-aware value through the session time zone; naive UTC cannot shift."""
    got = interval("2026-07-09T10:00:00Z")
    assert got is not None
    assert got[0].tzinfo is None


@pytest.mark.parametrize("value", ["", "July", "2026-13", "2026-07-32", "26-07-09", "2026-07-09Tnope", None, 3, True, ["2026"]])
def test_anything_else_is_not_a_time(value: object) -> None:
    assert interval(value) is None


@pytest.mark.parametrize("text", ["2026", "2026-07", "2026-12", "2026-02", "2026-07-09", "2026-07-09T10:00:00Z"])
def test_format_writes_the_precision_the_width_says(text: str) -> None:
    span = interval(text)
    assert span is not None
    assert format_interval(*span) == text
