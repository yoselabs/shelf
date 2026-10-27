"""timefmt — package-level unit tests.

Covers each of the four magnitude tiers and every boundary between them.
"""

from __future__ import annotations

import pytest
from timefmt import fmt_dur, fmt_until, human_count


@pytest.mark.parametrize(
    ("ms", "expected"),
    [
        # tier 1: < 1000 -> integer milliseconds
        (0, "0ms"),
        (1, "1ms"),
        (500, "500ms"),
        (999, "999ms"),
        # tier 2: 1000 <= ms < 7000 -> one decimal second
        (1000, "1.0s"),
        (1500, "1.5s"),
        (6999, "7.0s"),
        # tier 3: 7000 <= ms < 60_000 -> integer seconds (truncated)
        (7000, "7s"),
        (7999, "7s"),
        (12_500, "12s"),
        (59_999, "59s"),
        # tier 4: >= 60_000 -> {m}m{ss}s, seconds zero-padded
        (60_000, "1m00s"),
        (65_000, "1m05s"),
        (125_000, "2m05s"),
        (3_600_000, "60m00s"),
    ],
)
def test_fmt_dur(ms: int, expected: str) -> None:
    assert fmt_dur(ms) == expected


def test_zero_is_never_a_float() -> None:
    # The integer-ms floor exists so a zero duration reads "0ms", not "0.0s".
    assert fmt_dur(0) == "0ms"


def test_fmt_until_defaults_to_the_current_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("timefmt.time.time", lambda: 100.0)
    assert fmt_until(100.0 + 3 * 3600) == "3h00m"
    assert fmt_until(100.5) == "now"


def test_human_count_rounds_up_into_millions() -> None:
    assert human_count(999_500) == "1.0M"
    assert human_count(999_499) == "999k"
    assert human_count(999.9) == "999"
