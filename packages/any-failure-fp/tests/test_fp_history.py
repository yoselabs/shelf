from __future__ import annotations

from any_failure_fp import Event, Trip, seen_within, streak, trip


def ev(key: str, fp: str, t: float, kind: str = "fault") -> Event:
    return Event(key=key, fp=fp, t=t, kind=kind)


def test_same_fingerprint_on_enough_keys_inside_the_window_trips() -> None:
    history = [ev("a", "boom", 10.0), ev("b", "boom", 20.0)]
    got = trip(history, "c", "boom", 30.0, window_s=100, min_keys=3)
    assert got == Trip(fp="boom", keys=("a", "b", "c"), t=30.0)


def test_too_few_keys_or_other_fingerprints_do_not_trip() -> None:
    history = [ev("a", "one", 10.0), ev("b", "boom", 12.0)]
    assert trip(history, "c", "boom", 30.0, window_s=100, min_keys=3) is None


def test_the_same_key_repeating_is_not_a_storm() -> None:
    history = [ev("a", "boom", 10.0)] * 5
    assert trip(history, "a", "boom", 30.0, window_s=100, min_keys=2) is None


def test_old_events_fall_out_of_the_window() -> None:
    history = [ev("a", "boom", 1.0), ev("b", "boom", 90.0)]
    assert trip(history, "c", "boom", 200.0, window_s=120, min_keys=3) is None
    assert trip(history, "c", "boom", 200.0, window_s=250, min_keys=3) is not None


def test_count_filters_which_events_may_trip() -> None:
    history = [ev("a", "boom", 10.0, "pause"), ev("b", "boom", 11.0, "fault")]

    def only_faults(e: Event) -> bool:
        return e.kind == "fault"

    assert trip(history, "c", "boom", 30.0, window_s=100, min_keys=3, count=only_faults) is None
    assert trip(history, "c", "boom", 30.0, window_s=100, min_keys=3) is not None


def test_streak_counts_the_close_plus_matching_earlier_ones_for_the_key() -> None:
    history = [ev("b", "x", 1.0), ev("b", "x", 2.0), ev("c", "x", 3.0)]
    assert streak(history, "b", "x", stop=lambda e: e.kind == "ask") == 3
    assert streak(history, "c", "x", stop=lambda e: e.kind == "ask") == 2
    assert streak(history, "new", "x", stop=lambda e: e.kind == "ask") == 1


def test_a_stop_event_restarts_the_count() -> None:
    history = [ev("b", "x", 1.0), ev("b", "x", 2.0), ev("b", "x", 3.0, "ask"), ev("b", "x", 4.0)]
    assert streak(history, "b", "x", stop=lambda e: e.kind == "ask") == 2


def test_other_fingerprints_are_skipped_not_stopping() -> None:
    history = [ev("b", "x", 1.0), ev("b", "y", 2.0), ev("b", "x", 3.0)]
    assert streak(history, "b", "x", stop=lambda e: False) == 3


def test_seen_within_matches_key_kind_fp_and_age() -> None:
    history = [ev("b", "x", 1000.0, "pause")]
    assert seen_within(history, "b", "pause", "x", now=1500.0, window_s=3600)
    assert not seen_within(history, "b", "pause", "x", now=1000.0 + 3601, window_s=3600)
    assert not seen_within(history, "c", "pause", "x", now=1500.0, window_s=3600)
    assert not seen_within(history, "b", "fault", "x", now=1500.0, window_s=3600)
    assert not seen_within(history, "b", "pause", "y", now=1500.0, window_s=3600)
    assert seen_within(history, "b", "pause", "x", now=1000.0 + 3600, window_s=3600)
