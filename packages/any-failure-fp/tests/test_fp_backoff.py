from __future__ import annotations

import pytest

from any_failure_fp import backoff


def test_doubles_per_attempt_up_to_the_cap() -> None:
    assert [backoff(60, 3600, n, lambda: 0.5) for n in range(8)] == [60, 120, 240, 480, 960, 1920, 3600, 3600]


def test_jitter_spans_plus_minus_twenty_percent() -> None:
    assert backoff(100, 1000, 0, lambda: 0.0) == pytest.approx(80)
    assert backoff(100, 1000, 0, lambda: 1.0) == pytest.approx(120)
    assert backoff(100, 1000, 0, lambda: 0.5) == pytest.approx(100)


def test_jitter_is_tunable_and_can_be_off() -> None:
    assert backoff(100, 1000, 0, lambda: 0.0, jitter=0.5) == pytest.approx(50)
    assert backoff(100, 1000, 0, lambda: 0.0, jitter=0.0) == 100


def test_cap_applies_before_jitter() -> None:
    assert backoff(100, 150, 5, lambda: 1.0) == pytest.approx(180)


def test_a_huge_attempt_is_clamped_not_overflowing() -> None:
    assert backoff(30, 1800, 10**9, lambda: 0.5) == 1800
    assert backoff(30.0, 1800.0, 10**6, lambda: 0.5) == 1800


def test_negative_attempt_counts_as_zero() -> None:
    assert backoff(60, 3600, -4, lambda: 0.5) == 60
