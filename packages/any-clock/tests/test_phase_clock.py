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


def test_book_moves_seconds_out_of_the_owning_phase() -> None:
    tick = Tick()
    clock = PhaseClock(tick)
    tick.advance(10)
    assert clock.book("wait", 4) == 4
    assert clock.totals() == {"run": 6, "wait": 4}
    assert sum(clock.totals().values()) == pytest.approx(clock.wall())


def test_book_into_an_exempt_phase_reduces_charged() -> None:
    tick = Tick()
    clock = PhaseClock(tick, exempt={"wait"})
    tick.advance(10)
    assert clock.charged() == 10
    clock.book("wait", 3)
    assert clock.charged() == 7


def test_book_is_capped_at_what_the_donor_owns() -> None:
    tick = Tick()
    clock = PhaseClock(tick)
    tick.advance(2)
    assert clock.book("wait", 5) == 2
    assert clock.totals() == {"run": 0, "wait": 2}
    assert clock.book("wait", 1) == 0
    assert all(s >= 0 for s in clock.totals().values())


def test_book_keeps_the_invariant_while_time_moves() -> None:
    tick = Tick()
    clock = PhaseClock(tick, exempt={"wait"})
    tick.advance(3)
    clock.book("wait", 1)
    tick.advance(2)
    with clock.phase("a"):
        tick.advance(4)
        clock.book("wait", 1.5)
    tick.advance(1)
    assert sum(clock.totals().values()) == pytest.approx(clock.wall())


def test_book_donor_is_the_innermost_open_phase() -> None:
    tick = Tick()
    clock = PhaseClock(tick)
    tick.advance(10)
    with clock.phase("outer"):
        tick.advance(6)
        with clock.phase("inner"):
            tick.advance(4)
            assert clock.book("wait", 100) == 4
    assert clock.totals() == {"run": 10, "outer": 6, "inner": 0, "wait": 4}


def test_book_into_the_donor_itself_moves_nothing() -> None:
    tick = Tick()
    clock = PhaseClock(tick)
    tick.advance(5)
    assert clock.book("run", 3) == 0
    assert clock.totals() == {"run": 5}


def test_book_into_a_limited_phase_can_trip_over() -> None:
    tick = Tick()
    clock = PhaseClock(tick, {"wait": 2}, budget=5)
    tick.advance(10)
    assert clock.over() == [("charged", 10, 5)]
    clock.book("wait", 3)
    assert clock.over() == [("wait", 3, 2), ("charged", 10, 5)]


def test_book_into_an_exempt_phase_clears_a_budget_overrun() -> None:
    tick = Tick()
    clock = PhaseClock(tick, exempt={"wait"}, budget=5)
    tick.advance(8)
    assert clock.over() == [("charged", 8, 5)]
    clock.book("wait", 4)
    assert clock.over() == []


@pytest.mark.parametrize("seconds", [-1.0, 0.0, float("nan"), float("-inf")])
def test_book_of_nothing_or_nonsense_books_zero(seconds: float) -> None:
    tick = Tick()
    clock = PhaseClock(tick)
    tick.advance(5)
    assert clock.book("wait", seconds) == 0
    assert clock.totals() == {"run": 5}


def test_elapsed_starts_the_clock_part_way_owned_by_root() -> None:
    tick = Tick()
    clock = PhaseClock(tick, elapsed=90)
    assert clock.wall() == 90
    assert clock.totals() == {"run": 90}
    tick.advance(10)
    assert clock.wall() == 100
    assert sum(clock.totals().values()) == clock.wall()


def test_started_is_the_back_dated_reading() -> None:
    tick = Tick()
    assert PhaseClock(tick).started == 1000
    assert PhaseClock(tick, elapsed=250).started == 750


def test_restore_then_book_moves_the_waited_part_out_of_root() -> None:
    tick = Tick()
    clock = PhaseClock(tick, exempt={"wait"}, elapsed=600)
    assert clock.book("wait", 200) == 200
    tick.advance(60)
    assert clock.charged() == pytest.approx(460)
    assert clock.wall() == 660


def test_book_after_restore_is_capped_at_elapsed() -> None:
    tick = Tick()
    clock = PhaseClock(tick, elapsed=30)
    assert clock.book("wait", 100) == 30
    assert clock.totals() == {"run": 0, "wait": 30}


@pytest.mark.parametrize("elapsed", [-1.0, float("nan")])
def test_elapsed_must_be_a_non_negative_number(elapsed: float) -> None:
    with pytest.raises(ValueError, match="elapsed"):
        PhaseClock(Tick(), elapsed=elapsed)


def test_restored_clock_keeps_the_high_water_mark() -> None:
    tick = Tick()
    clock = PhaseClock(tick, elapsed=5)
    tick.advance(10)
    assert clock.wall() == 15
    tick.advance(-10)
    assert clock.wall() == 15


def test_concurrent_book_and_phase_lose_and_double_count_nothing() -> None:
    clock_t = [0.0]
    step = threading.Lock()

    def now() -> float:
        with step:  # every read moves time on, so threads really interleave
            clock_t[0] += 0.001
            return clock_t[0]

    clock = PhaseClock(now, exempt={"wait"}, elapsed=1000)
    errors: list[BaseException] = []
    start = threading.Barrier(16)

    def work(n: int) -> None:
        try:
            start.wait()
            for i in range(200):
                if n % 4 == 0:
                    with clock.phase(f"p{n}"):
                        clock.book("wait", 0.0005)
                else:
                    clock.book(f"lane{n}", 0.001)
                if i % 20 == 0:
                    assert sum(clock.totals().values()) == pytest.approx(clock.wall(), abs=0.5)
                    clock.over()
                    clock.charged()
        except BaseException as exc:  # noqa: BLE001 - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(n,)) for n in range(16)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert errors == []
    assert clock.current() == "run"
    totals = clock.totals()
    assert all(s >= 0 for s in totals.values())
    assert sum(totals.values()) == pytest.approx(clock.wall())
