"""Limit prose -> a reset time, and the guess when the message names none."""

import datetime as dt
import time

from any_agent.reset_parse import RESET_LADDER_MIN, limit_until, parse_reset

T = dt.datetime(2026, 10, 25, 3, 0, tzinfo=dt.UTC).timestamp()


def test_an_iso_time_with_a_zone_is_kept():
    at, zone = parse_reset("Usage limit reached. Your limit will reset at 2026-10-25T14:49:00Z", T)
    assert (at, zone) == (dt.datetime(2026, 10, 25, 14, 49, tzinfo=dt.UTC).timestamp(), "UTC")


def test_retry_after_seconds():
    assert parse_reset("429 Retry-After: 120", T) == (T + 120, None)


def test_in_hours_and_minutes():
    assert parse_reset("try again in 2 hours 30 min", T)[0] == T + 2 * 3600 + 30 * 60
    assert parse_reset("in 5 hours", T)[0] == T + 5 * 3600


def test_a_time_in_the_past_or_far_off_is_not_a_reset_time():
    assert parse_reset("will reset at 2020-01-01 00:00:00Z", T) == (None, None)
    assert parse_reset("will reset at 2030-01-01 00:00:00Z", T) == (None, None)
    assert parse_reset(None, T) == (None, None)


def test_a_limit_without_a_stated_end_is_guessed_on_a_ladder():
    assert limit_until("rate limited", T, {}) == (T + RESET_LADDER_MIN[0] * 60, "guess", None)
    assert limit_until("rate limited", T, {}, guess_n=1)[0] == T + RESET_LADDER_MIN[1] * 60
    assert limit_until("rate limited", T, {}, guess_n=9)[0] == T + RESET_LADDER_MIN[-1] * 60


def test_the_vendors_usage_reading_or_the_lanes_soonest_window_comes_before_the_ladder():
    assert limit_until("x", T, {}, reset=lambda: T + 99) == (T + 99, "vendor", None)
    assert limit_until("x", T, {"limit_reset": T + 500}) == (T + 500, "guess", None)
    assert limit_until("x", T, {}, reset=lambda: None)[1] == "guess"


def test_try_again_at_on_a_day_the_clocks_change_keeps_the_offset_of_the_time_named(monkeypatch):
    monkeypatch.setenv("TZ", "Europe/Berlin")
    time.tzset()
    try:
        at, _ = parse_reset("try again at 5:50 AM", dt.datetime(2026, 10, 25, 0, 0, tzinfo=dt.UTC).timestamp())  # DST ends at 03:00
        assert at is not None
        assert dt.datetime.fromtimestamp(at, dt.UTC).strftime("%H:%M") == "04:50"  # 05:50 CET
    finally:
        monkeypatch.undo()
        time.tzset()
