"""timefmt.parse_until / to_epoch — every input form and edge case."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest
from timefmt import parse_until, to_epoch

NOW = 1_700_000_000.0


@pytest.mark.parametrize(
    ("text", "offset"),
    [("+90m", 5400), ("+2h", 7200), ("+3d", 259_200), ("+0m", 0), ("  +2h ", 7200)],
)
def test_relative_units(text: str, offset: int) -> None:
    assert parse_until(text, NOW) == NOW + offset


@pytest.mark.parametrize("text", ["+5x", "+h", "+m", "+", "+-5m", "+1.5h", "+2H", "90m", "+ 2h"])
def test_bad_relative_is_none(text: str) -> None:
    assert parse_until(text, NOW) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1_700_000_000, 1_700_000_000.0),
        (1_700_000_000.5, 1_700_000_000.5),
        ("1700000000", 1_700_000_000.0),
        ("1700000000.5", 1_700_000_000.5),
        (1_700_000_000_000, 1_700_000_000.0),
        ("1700000000000", 1_700_000_000.0),
        ("90", 90.0),
    ],
)
def test_numbers_and_numeric_strings(value: object, expected: float) -> None:
    assert parse_until(value, NOW) == expected


def test_ms_threshold_is_exclusive() -> None:
    assert to_epoch(1e11) == 1e11
    assert to_epoch(1e11 + 1000) == 1e11 / 1000 + 1.0


def test_iso_with_z_and_offset_and_naive() -> None:
    expected = datetime(2026, 10, 24, 18, 0, tzinfo=UTC).timestamp()
    assert parse_until("2026-10-24T18:00:00Z", NOW) == expected
    assert parse_until("2026-10-24T18:00:00+00:00", NOW) == expected
    assert parse_until("2026-10-24T21:00:00+03:00", NOW) == expected
    assert to_epoch("2026-10-24T18:00:00") == datetime(2026, 10, 24, 18, 0).timestamp()  # noqa: DTZ001 - naive means local, by design


@pytest.mark.parametrize("value", [None, "", "   ", "garbage", "2026-13-45", [], b"x"])
def test_empty_and_garbage_are_none(value: object) -> None:
    assert parse_until(value, NOW) is None
    assert to_epoch(value) is None


@pytest.mark.parametrize("value", [True, False, math.nan, math.inf, -math.inf, "nan", "inf"])
def test_bool_and_non_finite_are_none(value: object) -> None:
    assert to_epoch(value) is None
    assert parse_until(value, NOW) is None


def test_zero_is_a_real_epoch() -> None:
    assert to_epoch(0) == 0.0
    assert parse_until(0, NOW) == 0.0
    assert parse_until("0", NOW) == 0.0


def test_to_epoch_converts_ms_and_seconds() -> None:
    assert to_epoch(1_700_000_000) == 1_700_000_000.0
    assert to_epoch(1_700_000_000_000) == 1_700_000_000.0
