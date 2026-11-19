"""The stored UTC stamp: byte-identical to the format any-speech has written since 0.1."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from any_clock import parse_stamp, utc_stamp

_OLD_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def test_utc_stamp_equals_the_stored_format_to_the_byte() -> None:
    moment = datetime(2026, 11, 20, 7, 5, 9, 987654, tzinfo=UTC)
    assert utc_stamp(moment) == moment.strftime(_OLD_FORMAT) == "2026-11-20T07:05:09Z"


def test_utc_stamp_converts_another_zone_to_utc() -> None:
    moment = datetime(2026, 11, 20, 10, 5, 9, tzinfo=timezone(timedelta(hours=3)))
    assert utc_stamp(moment) == "2026-11-20T07:05:09Z"


def test_utc_stamp_refuses_a_naive_datetime() -> None:
    with pytest.raises(ValueError, match="naive"):
        utc_stamp(datetime(2026, 11, 20, 7, 5, 9))  # noqa: DTZ001 -- the planted naive value


def test_parse_stamp_round_trips_and_is_aware() -> None:
    parsed = parse_stamp("2026-11-20T07:05:09Z")
    assert parsed == datetime(2026, 11, 20, 7, 5, 9, tzinfo=UTC)
    assert utc_stamp(parsed) == "2026-11-20T07:05:09Z"


_NOT_THE_STORED_SHAPE = [
    "2026-11-20",
    "2026-11-20T07:05:09",
    "2026-11-20 07:05:09Z",
    "2026-11-20T07:05:09+00:00",
    "2026-11-20T7:5:9Z",
    "",
]


@pytest.mark.parametrize("bad", _NOT_THE_STORED_SHAPE)
def test_parse_stamp_refuses_anything_but_the_stored_shape(bad: str) -> None:
    with pytest.raises(ValueError, match="stamp"):
        parse_stamp(bad)
