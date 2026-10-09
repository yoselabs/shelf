"""Schedule parsing and the due check — interval and cron forms. Moved from a2kay
(services/jobs/schedule.py)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from due_schedule import (
    cron_is_due,
    is_cron_like,
    is_due,
    is_valid_cron,
    parse_interval,
    schedule_is_due,
)


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("30s", timedelta(seconds=30)),
        ("15m", timedelta(minutes=15)),
        ("6h", timedelta(hours=6)),
        ("1d", timedelta(days=1)),
        ("  45m  ", timedelta(minutes=45)),  # surrounding whitespace tolerated
    ],
)
def test_parse_interval_units(spec: str, expected: timedelta) -> None:
    assert parse_interval(spec) == expected


@pytest.mark.parametrize("spec", ["", "abc", "10", "5x", "m", "-3h", "0s", "1.5h"])
def test_bad_interval_strings_return_none(spec: str) -> None:
    assert parse_interval(spec) is None


def test_cron_like_is_recognized_and_not_parsed_as_interval() -> None:
    cron = "*/5 * * * *"
    assert is_cron_like(cron) is True
    # A cron expression is never coerced to an interval; it routes through cron.
    assert parse_interval(cron) is None
    assert is_valid_cron(cron) is True
    # Interval strings are not mistaken for cron.
    assert is_cron_like("30s") is False


def test_is_due_first_run_is_immediate() -> None:
    now = datetime(2026, 6, 28, 9, 0, tzinfo=UTC)
    assert is_due(timedelta(minutes=15), None, now) is True


def test_is_due_when_interval_elapsed() -> None:
    interval = timedelta(minutes=15)
    last = datetime(2026, 6, 28, 9, 0, tzinfo=UTC)
    assert is_due(interval, last, last + timedelta(minutes=15)) is True
    assert is_due(interval, last, last + timedelta(minutes=20)) is True


def test_is_not_due_before_interval_elapsed() -> None:
    interval = timedelta(minutes=15)
    last = datetime(2026, 6, 28, 9, 0, tzinfo=UTC)
    assert is_due(interval, last, last + timedelta(minutes=14, seconds=59)) is False


# --- cron ---------------------------------------------------------------------


def test_cron_never_run_does_not_backfire() -> None:
    # A daily-at-03:00 job first seen at 14:00 must NOT fire immediately for the
    # 03:00 that already passed today — it waits for the next 03:00.
    now = datetime(2026, 6, 28, 14, 0, tzinfo=UTC)
    assert cron_is_due("0 3 * * *", None, now) is False


def test_cron_due_once_a_scheduled_fire_passed_since_last_run() -> None:
    spec = "0 3 * * *"  # daily at 03:00
    last = datetime(2026, 6, 28, 3, 0, tzinfo=UTC)
    # Same day 14:00: no new 03:00 has occurred since the last run.
    assert cron_is_due(spec, last, datetime(2026, 6, 28, 14, 0, tzinfo=UTC)) is False
    # Next day 03:00: a scheduled fire has passed → due.
    assert cron_is_due(spec, last, datetime(2026, 6, 29, 3, 0, tzinfo=UTC)) is True


def test_cron_step_expression() -> None:
    spec = "*/15 * * * *"  # every 15 minutes
    last = datetime(2026, 6, 28, 9, 0, tzinfo=UTC)
    assert cron_is_due(spec, last, datetime(2026, 6, 28, 9, 14, tzinfo=UTC)) is False
    assert cron_is_due(spec, last, datetime(2026, 6, 28, 9, 15, tzinfo=UTC)) is True


def test_invalid_cron_is_never_due() -> None:
    now = datetime(2026, 6, 28, 9, 0, tzinfo=UTC)
    assert cron_is_due("nonsense * *", None, now) is False
    assert is_valid_cron("nonsense * *") is False


# --- schedule_is_due routing --------------------------------------------------


def test_schedule_is_due_routes_interval() -> None:
    last = datetime(2026, 6, 28, 9, 0, tzinfo=UTC)
    assert schedule_is_due("15m", last, last + timedelta(minutes=15)) is True
    assert schedule_is_due("15m", last, last + timedelta(minutes=10)) is False


def test_schedule_is_due_routes_cron() -> None:
    last = datetime(2026, 6, 28, 3, 0, tzinfo=UTC)
    assert schedule_is_due("0 3 * * *", last, datetime(2026, 6, 29, 3, 0, tzinfo=UTC)) is True
    assert schedule_is_due("0 3 * * *", last, datetime(2026, 6, 28, 14, 0, tzinfo=UTC)) is False


@pytest.mark.parametrize("spec", [None, "", "garbage", "99x"])
def test_schedule_is_due_false_for_no_or_invalid_schedule(spec: str | None) -> None:
    now = datetime(2026, 6, 28, 9, 0, tzinfo=UTC)
    assert schedule_is_due(spec, None, now) is False


def test_a_cron_spec_with_surrounding_whitespace_is_read() -> None:
    last = datetime(2026, 6, 28, 3, 0, tzinfo=UTC)
    assert is_valid_cron("  0 3 * * *  ") is True
    assert schedule_is_due("  0 3 * * *  ", last, datetime(2026, 6, 29, 3, 0, tzinfo=UTC)) is True


def test_no_spec_is_neither_cron_nor_valid() -> None:
    assert is_cron_like(None) is False
    assert is_cron_like("") is False
    assert is_valid_cron(None) is False
    assert parse_interval(None) is None


def test_an_interval_job_never_run_is_due_through_the_router() -> None:
    assert schedule_is_due("1d", None, datetime(2026, 6, 28, 9, 0, tzinfo=UTC)) is True
