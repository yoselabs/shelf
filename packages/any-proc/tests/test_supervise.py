"""The supervisor state machine, on a fake child, a scripted probe and a hand-driven clock."""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

from any_proc.supervise import Health, State, Supervisor, rotate_log

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


class FakeProc:
    """A stand-in child: ``poll()`` is None while alive, else the exit code."""

    def __init__(self, *, alive: bool = True, exit_code: int = 0, stuck: bool = False) -> None:
        self.alive = alive
        self.exit_code = exit_code
        self.stuck = stuck
        self.terminated = False
        self.killed = False
        self.waited = False

    def poll(self) -> int | None:
        return None if self.alive else self.exit_code

    def terminate(self) -> None:
        self.terminated = True
        if not self.stuck:
            self.alive = False

    def kill(self) -> None:
        self.killed = True
        self.alive = False

    def wait(self, timeout: float | None = None) -> int:
        self.waited = True
        if self.stuck:
            msg = "still running"
            raise TimeoutError(msg)
        return self.exit_code


class ScriptedProbe:
    """Returns queued verdicts in order, repeating the last one."""

    def __init__(self, *health: Health) -> None:
        self._queue = list(health)

    def __call__(self) -> Health:
        return self._queue.pop(0) if len(self._queue) > 1 else self._queue[0]


class MutClock:
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


class FakeClock:
    def __init__(self, *times: float) -> None:
        self._it = iter(times)

    def __call__(self) -> float:
        return next(self._it, 999.0)


def _counting_spawn(procs: list[FakeProc]) -> tuple[Callable[[], FakeProc], list[FakeProc]]:
    spawned: list[FakeProc] = []

    def spawn() -> FakeProc:
        p = procs[len(spawned)]
        spawned.append(p)
        return p

    return spawn, spawned


def _sup(spawn: Callable[[], FakeProc], probe: ScriptedProbe, **kw: object) -> Supervisor:
    kw.setdefault("clock", MutClock())
    return Supervisor(spawn, probe, sleep=lambda _s: None, **kw)  # type: ignore[arg-type]


def test_start_success_is_up_with_the_version() -> None:
    s = _sup(FakeProc, ScriptedProbe(Health("up", version="1.2")))
    assert s.start() is State.up
    assert s.version == "1.2"


def test_spawn_failure_settles_down_without_raising() -> None:
    def boom() -> FakeProc:
        msg = "no exec"
        raise OSError(msg)

    s = _sup(boom, ScriptedProbe(Health("down")))
    assert s.start() is State.down
    assert s.reason == "spawn failed: no exec"


def test_an_early_exit_is_down_with_the_code_by_default() -> None:
    s = _sup(lambda: FakeProc(alive=False, exit_code=3), ScriptedProbe(Health("up")))
    assert s.start() is State.down
    assert s.reason == "child exited (code 3)"


def test_an_exit_the_consumer_classifies_terminal_is_terminal_and_named() -> None:
    s = _sup(
        lambda: FakeProc(alive=False, exit_code=1),
        ScriptedProbe(Health("up")),
        classify_exit=lambda code: Health("conflict", reason=f"lock held ({code})"),
    )
    assert s.start() is State.terminal
    assert s.terminal == "conflict"
    assert s.reason == "lock held (1)"


def test_startup_timeout_terminates_the_child() -> None:
    proc = FakeProc(alive=True)
    s = _sup(lambda: proc, ScriptedProbe(Health("down")), startup_timeout=1.0, clock=FakeClock(0.0, 0.0, 5.0))
    assert s.start() is State.down
    assert s.reason == "startup timed out"
    assert proc.terminated


def test_start_keeps_polling_while_the_probe_says_down() -> None:
    slept: list[float] = []
    probe = ScriptedProbe(Health("down"), Health("down"), Health("up"))
    s = Supervisor(FakeProc, probe, sleep=slept.append, clock=MutClock(), poll_interval=0.25)
    assert s.start() is State.up
    assert slept == [0.25, 0.25]


def test_a_terminal_probe_verdict_during_start_is_terminal() -> None:
    s = _sup(FakeProc, ScriptedProbe(Health("skewed", version="0.9", reason="older")))
    assert s.start() is State.terminal
    assert (s.terminal, s.version, s.reason) == ("skewed", "0.9", "older")


def test_poll_detects_child_death() -> None:
    proc = FakeProc(alive=True)
    s = _sup(lambda: proc, ScriptedProbe(Health("up")))
    s.start()
    proc.alive, proc.exit_code = False, 137
    assert s.poll_once().status == "down"
    assert s.state is State.down


def test_poll_before_start_is_down_not_started() -> None:
    s = _sup(FakeProc, ScriptedProbe(Health("up")))
    assert s.poll_once() == Health("down", reason="not started")


def test_poll_surfaces_a_terminal_verdict_without_touching_the_child() -> None:
    proc = FakeProc(alive=True)
    s = _sup(lambda: proc, ScriptedProbe(Health("up", version="2"), Health("skewed", version="1", reason="older")))
    s.start()
    assert s.poll_once().status == "skewed"
    assert s.state is State.terminal
    assert not proc.terminated


def test_stop_is_graceful_then_idle() -> None:
    proc = FakeProc(alive=True)
    s = _sup(lambda: proc, ScriptedProbe(Health("up")))
    s.start()
    assert s.stop() is State.idle
    assert proc.terminated
    assert proc.waited
    assert not proc.killed


def test_stop_kills_a_child_that_outlives_the_wait() -> None:
    proc = FakeProc(alive=True, stuck=True)
    s = _sup(lambda: proc, ScriptedProbe(Health("up")))
    s.start()
    assert s.stop(timeout=0.1) is State.idle
    assert proc.killed


def test_stop_without_a_child_is_idle() -> None:
    assert _sup(FakeProc, ScriptedProbe(Health("up"))).stop() is State.idle


def test_restart_stops_then_starts_a_fresh_child() -> None:
    spawn, spawned = _counting_spawn([FakeProc(), FakeProc()])
    s = _sup(spawn, ScriptedProbe(Health("up")))
    s.start()
    assert s.restart() is State.up
    assert len(spawned) == 2
    assert spawned[0].terminated
    assert spawned[1].alive


def test_supervise_respawns_a_crashed_child() -> None:
    spawn, spawned = _counting_spawn([FakeProc(), FakeProc()])
    s = _sup(spawn, ScriptedProbe(Health("up")))
    s.start()
    spawned[0].alive, spawned[0].exit_code = False, 137
    assert s.supervise() is State.up
    assert len(spawned) == 2


def test_supervise_bounds_a_crash_loop_but_retries_next_window() -> None:
    clock = MutClock(0.0)
    spawn, spawned = _counting_spawn([FakeProc(alive=False, exit_code=1) for _ in range(20)])
    s = _sup(spawn, ScriptedProbe(Health("up")), clock=clock, restart_budget=3, restart_window=60.0, restart_base=1.0, restart_cap=30.0)
    assert s.start() is State.down
    in_setup = len(spawned)
    for t in (0.0, 1.0, 3.0, 7.0, 8.0, 15.0):
        clock.t = t
        s.supervise()
    assert len(spawned) - in_setup == 3
    assert s.state is State.down
    assert s.reason == "restart budget exhausted: 3 in 60s"
    clock.t = 100.0
    s.supervise()
    assert len(spawned) - in_setup == 4


def test_backoff_doubles_and_is_capped() -> None:
    clock = MutClock(0.0)
    spawn, spawned = _counting_spawn([FakeProc(alive=False, exit_code=1) for _ in range(20)])
    s = _sup(spawn, ScriptedProbe(Health("up")), clock=clock, restart_budget=10, restart_window=1000.0, restart_base=1.0, restart_cap=3.0)
    s.start()
    fired: list[float] = []
    for tick in range(40):
        clock.t = tick * 0.5
        before = len(spawned)
        s.supervise()
        if len(spawned) > before:
            fired.append(clock.t)
    gaps = [b - a for a, b in itertools.pairwise(fired)]
    assert gaps[:3] == [1.0, 2.0, 3.0]
    assert max(gaps) == 3.0


def test_supervise_never_respawns_a_terminal_exit() -> None:
    clock = MutClock()
    spawn, spawned = _counting_spawn([FakeProc(alive=False, exit_code=1) for _ in range(5)])
    s = _sup(spawn, ScriptedProbe(Health("up")), clock=clock, classify_exit=lambda _c: Health("conflict"))
    assert s.start() is State.terminal
    for t in (0.0, 5.0, 100.0):
        clock.t = t
        assert s.supervise() is State.terminal
    assert len(spawned) == 1


def test_supervise_leaves_a_terminal_probe_verdict_untouched() -> None:
    spawn, spawned = _counting_spawn([FakeProc()])
    s = _sup(spawn, ScriptedProbe(Health("up"), Health("skewed")))
    s.start()
    assert s.supervise() is State.terminal
    assert s.supervise() is State.terminal
    assert len(spawned) == 1
    assert spawned[0].alive


def test_poll_once_never_respawns() -> None:
    spawn, spawned = _counting_spawn([FakeProc()])
    s = _sup(spawn, ScriptedProbe(Health("up")))
    s.start()
    spawned[0].alive = False
    assert s.poll_once().status == "down"
    assert len(spawned) == 1


def test_a_healthy_up_resets_the_restart_budget() -> None:
    clock = MutClock(0.0)
    spawn, _ = _counting_spawn([FakeProc(alive=False, exit_code=1), FakeProc(alive=False, exit_code=1), FakeProc()])
    s = _sup(spawn, ScriptedProbe(Health("up")), clock=clock, restart_budget=2)
    s.start()
    s.supervise()
    clock.t = 5.0
    s.supervise()
    assert s.state is State.up
    clock.t = 6.0
    s.supervise()
    assert s._restart_times == []


def test_a_live_child_that_stops_answering_is_unresponsive_and_not_respawned() -> None:
    spawn, spawned = _counting_spawn([FakeProc(), FakeProc()])
    s = _sup(spawn, ScriptedProbe(Health("up"), Health("down", reason="probe timed out")))
    s.start()
    for _ in range(3):
        assert s.supervise() is State.unresponsive
    assert s.reason == "probe timed out"
    assert len(spawned) == 1


def test_an_unresponsive_child_that_answers_again_is_up_with_the_budget_reset() -> None:
    spawn, spawned = _counting_spawn([FakeProc()])
    s = _sup(spawn, ScriptedProbe(Health("up"), Health("down"), Health("down"), Health("up")))
    s.start()
    s._restart_times = [0.0]
    assert s.supervise() is State.unresponsive
    assert s.supervise() is State.unresponsive
    assert s.supervise() is State.up
    assert s._restart_times == []
    assert len(spawned) == 1


def test_an_unresponsive_child_that_exits_is_respawned() -> None:
    spawn, spawned = _counting_spawn([FakeProc(), FakeProc()])
    s = _sup(spawn, ScriptedProbe(Health("up"), Health("down"), Health("up")))
    s.start()
    assert s.supervise() is State.unresponsive
    spawned[0].alive, spawned[0].exit_code = False, 137
    assert s.supervise() is State.up
    assert len(spawned) == 2


def test_start_never_spawns_over_a_live_child() -> None:
    spawn, spawned = _counting_spawn([FakeProc(), FakeProc()])
    s = _sup(spawn, ScriptedProbe(Health("up"), Health("down")))
    s.start()
    s.supervise()
    assert s.start() is State.unresponsive
    assert len(spawned) == 1


def test_idle_is_not_supervised() -> None:
    spawn, spawned = _counting_spawn([FakeProc()])
    s = _sup(spawn, ScriptedProbe(Health("up")))
    assert s.supervise() is State.idle
    assert spawned == []


def test_log_rotates_so_each_run_starts_clean(tmp_path: Path) -> None:
    log = tmp_path / "child.log"
    rotate_log(log)  # nothing yet: a no-op
    assert not log.exists()
    log.write_text("run A\n")
    rotate_log(log)
    log.write_text("run B\n")
    rotate_log(log)
    log.write_text("run C\n")
    assert (tmp_path / "child.log.1").read_text() == "run B\n"
    assert (tmp_path / "child.log.2").read_text() == "run A\n"
    rotate_log(log)
    assert not (tmp_path / "child.log.3").exists()
    assert (tmp_path / "child.log.2").read_text() == "run B\n"
    assert (tmp_path / "child.log.1").read_text() == "run C\n"
