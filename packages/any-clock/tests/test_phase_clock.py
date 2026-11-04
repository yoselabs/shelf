from __future__ import annotations

import threading

import pytest

from any_clock import PhaseClock


class Tick:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, secs: float) -> None:
        self.t += secs


def test_unphased_time_belongs_to_root() -> None:
    tick = Tick()
    clock = PhaseClock(tick)
    tick.advance(5)
    assert clock.current() == "run"
    assert clock.total("run") == 5
    assert clock.total("never") == 0


def test_inner_phase_pauses_outer() -> None:
    tick = Tick()
    clock = PhaseClock(tick)
    tick.advance(1)
    with clock.phase("review"):
        tick.advance(2)
        with clock.phase("push"):
            assert clock.current() == "push"
            tick.advance(4)
        assert clock.current() == "review"
        tick.advance(8)
    assert clock.totals() == {"run": 1, "review": 10, "push": 4}


def test_total_is_live_inside_an_open_phase() -> None:
    tick = Tick()
    clock = PhaseClock(tick)
    with clock.phase("lane"):
        tick.advance(3)
        assert clock.total("lane") == 3
        tick.advance(3)
        assert clock.total("lane") == 6


def test_totals_add_up_to_wall_time() -> None:
    tick = Tick()
    clock = PhaseClock(tick)
    for name, secs in [("a", 1.5), ("b", 2.25), ("a", 0.5)]:
        tick.advance(0.75)
        with clock.phase(name):
            tick.advance(secs)
            with clock.phase("c"):
                tick.advance(secs / 2)
    tick.advance(1)
    assert sum(clock.totals().values()) == pytest.approx(clock.wall())


def test_exception_leaves_the_phase_and_books_its_time() -> None:
    tick = Tick()
    clock = PhaseClock(tick)
    with pytest.raises(ValueError), clock.phase("push"):
        tick.advance(7)
        raise ValueError
    assert clock.current() == "run"
    tick.advance(2)
    assert clock.totals() == {"run": 2, "push": 7}


def test_charged_skips_exempt_phases() -> None:
    tick = Tick()
    clock = PhaseClock(tick, exempt={"lane", "network"})
    tick.advance(10)
    with clock.phase("lane"):
        tick.advance(100)
    with clock.phase("review"):
        tick.advance(5)
    assert clock.charged() == 15


def test_over_reports_only_limited_phases_past_their_limit() -> None:
    tick = Tick()
    clock = PhaseClock(tick, {"review": 5, "push": 60})
    with clock.phase("review"):
        tick.advance(5)
    assert clock.over() == []
    with clock.phase("review"):
        tick.advance(1)
    with clock.phase("other"):
        tick.advance(1000)
    assert clock.over() == [("review", 6, 5)]


def test_clock_stepping_back_never_books_negative_time() -> None:
    tick = Tick()
    clock = PhaseClock(tick)
    tick.advance(-50)
    assert clock.total("run") == 0


def test_clock_stepping_back_then_forward_books_each_second_once() -> None:
    tick = Tick()
    clock = PhaseClock(tick)
    tick.advance(10)
    assert clock.total("run") == 10
    tick.advance(-10)
    assert clock.total("run") == 10
    tick.advance(15)
    assert clock.totals() == {"run": 15}
    assert sum(clock.totals().values()) == clock.wall() == 15


def test_budget_limits_charged_time_only() -> None:
    tick = Tick()
    clock = PhaseClock(tick, exempt={"lane"}, budget=10)
    with clock.phase("lane"):
        tick.advance(100)
    tick.advance(10)
    assert clock.over() == []
    tick.advance(1)
    assert clock.over() == [("charged", 11, 10)]


def test_phase_named_like_the_root_and_same_name_nesting() -> None:
    tick = Tick()
    clock = PhaseClock(tick)
    with clock.phase("run"):
        tick.advance(1)
        with clock.phase("run"):
            tick.advance(2)
    with clock.phase("a"), clock.phase("a"):
        tick.advance(4)
    assert clock.totals() == {"run": 3, "a": 4}
    assert clock.current() == "run"


def test_clock_raising_inside_the_exit_still_pops_the_phase() -> None:
    tick = Tick()
    broken = False

    def now() -> float:
        if broken:
            raise OSError
        return tick()

    clock = PhaseClock(now)
    with pytest.raises(OSError), clock.phase("x"):
        broken = True
    broken = False
    assert clock.current() == "run"


def test_other_thread_is_refused() -> None:
    clock = PhaseClock(Tick())
    errors: list[BaseException] = []

    def enter() -> None:
        try:
            with clock.phase("x"):
                pass
        except RuntimeError as exc:
            errors.append(exc)

    worker = threading.Thread(target=enter)
    worker.start()
    worker.join()
    assert len(errors) == 1
    assert clock.current() == "run"
