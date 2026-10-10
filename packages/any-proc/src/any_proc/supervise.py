"""Keep one long-lived child alive.

:class:`Supervisor` spawns a child, polls a probe until it answers or a start timeout
passes, stops it gracefully (SIGTERM, then SIGKILL after a wait), and on a recoverable
death respawns it under capped exponential backoff and a restart budget over a rolling
window. It never raises out of ``start``: every failure settles a state with a reason.

A probe answers with a :class:`Health`. ``"up"`` and ``"down"`` are the supervisor's
own; any other status is **terminal** — a verdict a respawn cannot change (another owner
holds a lock, the running version is not ours while others are attached) — and the
supervisor stops touching the child until a person acts. The consumer names its terminal
verdicts; the supervisor only keeps the name.

All effects are injected (spawn, probe, exit classification, sleep, clock), so the state
machine is tested with a fake child and a scripted probe. :func:`rotate_log` is the
log-per-run helper a spawn function calls before opening its log.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


class State(StrEnum):
    """The supervised child's lifecycle state."""

    idle = "idle"
    starting = "starting"
    up = "up"
    #: Alive but not answering its probe. Never respawned: a second child next to a live
    #: one could only fight it for whatever the first one holds.
    unresponsive = "unresponsive"
    down = "down"
    #: A probe or exit verdict a respawn cannot change; :attr:`Supervisor.terminal` names it.
    terminal = "terminal"
    stopping = "stopping"


@dataclass(frozen=True)
class Health:
    """One verdict about the child: ``"up"``, ``"down"``, or the consumer's name for a
    terminal verdict."""

    status: str
    version: str | None = None
    reason: str | None = None


class Child(Protocol):
    """The slice of ``subprocess.Popen`` the supervisor uses."""

    def poll(self) -> int | None: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...
    def wait(self, timeout: float | None = ...) -> int: ...


def _exited(code: int) -> Health:
    return Health("down", reason=f"child exited (code {code})")


class Supervisor:
    """Supervises one child.

    ``spawn`` starts a child; ``probe`` asks it for :class:`Health`; ``classify_exit``
    turns an exit code into a verdict (default: a recoverable ``down``), which is where a
    consumer recognises an exit no respawn can fix.
    """

    def __init__(
        self,
        spawn: Callable[[], Child],
        probe: Callable[[], Health],
        *,
        classify_exit: Callable[[int], Health] = _exited,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        startup_timeout: float = 30.0,
        poll_interval: float = 0.5,
        restart_budget: int = 5,
        restart_window: float = 60.0,
        restart_base: float = 1.0,
        restart_cap: float = 30.0,
    ) -> None:
        self._spawn = spawn
        self._probe = probe
        self._classify_exit = classify_exit
        self._sleep = sleep
        self._clock = clock
        self.startup_timeout = startup_timeout
        self.poll_interval = poll_interval
        self.restart_budget = restart_budget
        self.restart_window = restart_window
        self.restart_base = restart_base
        self.restart_cap = restart_cap

        self.state = State.idle
        #: The terminal verdict's name while ``state`` is :attr:`State.terminal`, else None.
        self.terminal: str | None = None
        self.reason: str | None = None
        self.version: str | None = None
        self._proc: Child | None = None
        self._restart_times: list[float] = []  # clock-times of recent respawns (rolling window)
        self._backoff_until: float = 0.0  # earliest clock-time the next respawn may fire

    def start(self) -> State:
        """Spawn the child and poll until it is up, settling ``down`` on failure.

        A spawn failure, an early exit and a start timeout all settle ``down`` with a
        reason (or terminal, when the exit classifies so). Never spawns over a live child.
        """
        if self.state in (State.up, State.starting) or (self._proc is not None and self._proc.poll() is None):
            return self.state
        self.state = State.starting
        self.terminal = None
        self.reason = None
        try:
            proc = self._spawn()
        except Exception as exc:  # noqa: BLE001 — any spawn failure is a clean `down`, never a raise
            return self._settle_down(f"spawn failed: {exc}")
        self._proc = proc

        deadline = self._clock() + self.startup_timeout
        while self._clock() < deadline:
            code = proc.poll()
            if code is not None:
                self._apply(self._classify_exit(code))
                return self.state
            health = self._probe()
            if health.status != "down":
                self._apply(health)
                return self.state
            self._sleep(self.poll_interval)

        proc.terminate()
        return self._settle_down("startup timed out")

    def stop(self, timeout: float = 10.0) -> State:
        """SIGTERM the child so it can tear down in order; SIGKILL it if it outlives ``timeout``."""
        proc = self._proc
        if proc is None:
            self.state = State.idle
            return self.state
        self.state = State.stopping
        proc.terminate()
        try:
            proc.wait(timeout)
        except Exception:  # noqa: BLE001 — a stuck child must not wedge the stop; escalate
            proc.kill()
        self._proc = None
        self.terminal = None
        self.reason = None
        self.version = None
        self.state = State.idle
        return self.state

    def restart(self) -> State:
        """Stop the current child, if any, and start a fresh one (what a person asks for)."""
        self.stop()
        return self.start()

    def poll_once(self) -> Health:
        """One health read, updating ``state``; never respawns.

        A dead child is classified by its exit whatever the probe would say. A live child
        whose probe says ``down`` is ``unresponsive``, not down.
        """
        proc = self._proc
        if proc is None:
            return self._apply(Health("down", reason="not started"))
        code = proc.poll()
        if code is not None:
            return self._apply(self._classify_exit(code))
        health = self._probe()
        if health.status == "down":
            self.state = State.unresponsive
            self.terminal = None
            self.reason = health.reason
            return health
        return self._apply(health)

    def supervise(self) -> State:
        """Read health and respawn a recoverably dead child (the timer step).

        Respawns under capped exponential backoff and at most ``restart_budget`` times per
        ``restart_window``; an exhausted budget settles ``down`` with the count. A healthy
        ``up`` forgives the past. Terminal, unresponsive, idle and stopping are left alone.
        """
        if self.state in (State.terminal, State.stopping, State.idle):
            return self.state
        health = self.poll_once()
        if health.status == "up":
            self._restart_times.clear()
            self._backoff_until = 0.0
            return self.state
        if self.state in (State.terminal, State.unresponsive):
            return self.state
        now = self._clock()
        if now < self._backoff_until:
            return self.state
        self._restart_times = [t for t in self._restart_times if now - t < self.restart_window]
        if len(self._restart_times) >= self.restart_budget:
            return self._settle_down(f"restart budget exhausted: {len(self._restart_times)} in {self.restart_window:g}s")
        self._restart_times.append(now)
        self._backoff_until = now + min(self.restart_base * 2.0 ** (len(self._restart_times) - 1), self.restart_cap)
        self.start()
        return self.state

    def _apply(self, health: Health) -> Health:
        if health.status == "up":
            self.state, self.terminal = State.up, None
        elif health.status == "down":
            self.state, self.terminal = State.down, None
        else:
            self.state, self.terminal = State.terminal, health.status
        self.version = health.version if health.version is not None else self.version
        self.reason = health.reason
        return health

    def _settle_down(self, reason: str) -> State:
        self.reason = reason
        self.terminal = None
        self.state = State.down
        return self.state


def rotate_log(path: Path, keep: int = 2) -> None:
    """Roll ``log`` → ``log.1`` → … → ``log.<keep>``, dropping the oldest, before a fresh run.

    Open the log truncating after this, so each run's log holds only that run. A no-op
    when the log does not exist yet.
    """
    if not path.exists():
        return
    path.with_name(f"{path.name}.{keep}").unlink(missing_ok=True)
    for i in range(keep - 1, 0, -1):
        src = path.with_name(f"{path.name}.{i}")
        if src.exists():
            src.rename(path.with_name(f"{path.name}.{i + 1}"))
    path.rename(path.with_name(f"{path.name}.1"))


__all__ = ["Child", "Health", "State", "Supervisor", "rotate_log"]
