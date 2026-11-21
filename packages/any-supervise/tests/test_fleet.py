"""The verbs against real short-lived child processes."""

from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from stream_proc import alive, proc_start, stop_pid

from any_supervise import (
    BusyError,
    Host,
    ReplacementDiedError,
    Spec,
    State,
    StateError,
    UnknownNameError,
    down,
    load_spec,
    logs,
    roll,
    status,
    up,
)
from any_supervise.fleet import _locked
from any_supervise.model import SuperviseError
from any_supervise.store import path_of, read, write
from any_supervise.testing import ManualClock

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

WORKER = Path(__file__).parent / "_worker.py"


@dataclasses.dataclass
class Fleet:
    root: Path
    spec: Spec
    clock: ManualClock
    host: Host

    def set_version(self, version: str) -> None:
        (self.root / "VERSION").write_text(version + "\n", encoding="utf-8")

    def pid(self, name: str) -> int:
        rec = read(self.spec, name)
        assert rec is not None
        return rec.pid

    def alive(self, name: str) -> bool:
        rec = read(self.spec, name)
        return rec is not None and alive(rec.pid, rec.start)

    def wait_ready(self, name: str, *, count: int = 1) -> None:
        log = next(r.log for r in self.spec.replicas if r.name == name)
        deadline = time.monotonic() + 15
        while log.read_text(encoding="utf-8").count("ready") < count if log.exists() else True:
            assert time.monotonic() < deadline, f"{name} never said ready"
            time.sleep(0.02)


def write_spec(
    root: Path, *, mode: str = "sleep", count: int = 2, stop_timeout_s: float = 5, args: tuple[str, ...] = (), extra: str = ""
) -> Path:
    spec = root / "fleet.toml"
    probe = json.dumps([sys.executable, "-c", "print(open('VERSION').read().strip())"])
    command = json.dumps([sys.executable, str(WORKER), mode, *args])
    spec.write_text(
        f"""state = "state"
version_cmd = {probe}
version_cwd = "."

[[worker]]
name = "w"
command = {command}
count = {count}
cwd = "."
log = "logs"
stop_timeout_s = {stop_timeout_s}
{extra}
""",
        encoding="utf-8",
    )
    return spec


@pytest.fixture
def make_fleet(tmp_path: Path) -> Iterator[object]:
    made: list[Fleet] = []

    def make(**kwargs: Any) -> Fleet:
        (tmp_path / "VERSION").write_text("v1\n", encoding="utf-8")
        clock = ManualClock()
        spec = load_spec(write_spec(tmp_path, **kwargs))
        fleet = Fleet(tmp_path, spec, clock, Host(environ=os.environ, clock=clock, sleep=clock.sleep))
        made.append(fleet)
        return fleet

    yield make
    for fleet in made:
        with contextlib.suppress(SuperviseError, ExceptionGroup):
            down(fleet.spec)


type Make = Callable[..., Fleet]


def states(fleet: Fleet) -> dict[str, State]:
    return {r.name: r.state for r in status(fleet.spec, fleet.host)}


def test_up_starts_every_replica_and_is_idempotent(make_fleet: Make) -> None:
    fleet = make_fleet(count=3)
    first = up(fleet.spec, fleet.host)
    assert [s.name for s in first] == ["w-1", "w-2", "w-3"]
    pids = {n: fleet.pid(n) for n in ("w-1", "w-2", "w-3")}
    assert up(fleet.spec, fleet.host) == ()
    assert {n: fleet.pid(n) for n in pids} == pids
    assert set(states(fleet).values()) == {State.RUNNING}


def test_a_state_file_records_identity_version_and_time(make_fleet: Make) -> None:
    fleet = make_fleet(count=1)
    up(fleet.spec, fleet.host)
    rec = read(fleet.spec, "w-1")
    assert rec is not None
    assert rec.start == proc_start(rec.pid)
    assert (rec.version, rec.started_at) == ("v1", fleet.clock.now)
    assert json.loads(path_of(fleet.spec, "w-1").read_text())["argv"][-1] == "sleep"


def test_version_drift_shows_stale_without_the_worker_cooperating(make_fleet: Make) -> None:
    fleet = make_fleet(count=2)
    up(fleet.spec, fleet.host)
    fleet.set_version("v2")
    rows = status(fleet.spec, fleet.host)
    assert {r.state for r in rows} == {State.STALE}
    assert {(r.version, r.current) for r in rows} == {("v1", "v2")}
    assert up(fleet.spec, fleet.host) == ()  # up never restarts a live replica; roll does


def test_a_dead_replica_is_dead_and_up_restarts_only_it(make_fleet: Make) -> None:
    fleet = make_fleet(count=2)
    up(fleet.spec, fleet.host)
    keep, victim = fleet.pid("w-1"), fleet.pid("w-2")
    rec = read(fleet.spec, "w-2")
    assert rec is not None
    down(fleet.spec, "w-2")
    write(fleet.spec, rec)  # the file of a replica whose process is gone
    assert states(fleet) == {"w-1": State.RUNNING, "w-2": State.DEAD}
    assert [s.name for s in up(fleet.spec, fleet.host)] == ["w-2"]
    assert fleet.pid("w-1") == keep
    assert fleet.pid("w-2") != victim


def test_a_replica_without_a_state_file_is_missing(make_fleet: Make) -> None:
    fleet = make_fleet(count=1)
    assert states(fleet) == {"w-1": State.MISSING}


def test_a_recycled_pid_is_not_ours_and_is_never_signalled(make_fleet: Make) -> None:
    fleet = make_fleet(count=1, stop_timeout_s=1)
    stranger = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
    try:
        real = proc_start(stranger.pid)
        assert real is not None
        path_of(fleet.spec, "w-1").parent.mkdir(parents=True, exist_ok=True)
        path_of(fleet.spec, "w-1").write_text(
            json.dumps(
                {"name": "w-1", "pid": stranger.pid, "start": "not-its-start-time", "argv": ["x"], "version": "v1", "started_at": 1.0}
            ),
        )
        assert states(fleet) == {"w-1": State.DEAD}
        fleet.set_version("v2")
        roll(fleet.spec, fleet.host, names=["w-1"], settle_s=0.1)  # the old record is not a live process of ours: only a start
        started = read(fleet.spec, "w-1")
        assert started is not None
        assert stop_pid(started.pid, started.start, grace=2) == ()  # the replacement is ours; stop it before the file is overwritten
        assert stranger.poll() is None
        assert alive(stranger.pid, real)
        path_of(fleet.spec, "w-1").write_text(
            json.dumps({"name": "w-1", "pid": stranger.pid, "start": "again-not-its", "argv": ["x"], "version": "v1", "started_at": 1.0}),
        )
        assert [s.pid for s in down(fleet.spec, "w-1")] == [stranger.pid]
        assert stranger.poll() is None
    finally:
        stranger.kill()
        stranger.wait()


def test_a_process_with_no_state_file_is_never_touched(make_fleet: Make) -> None:
    fleet = make_fleet(count=1)
    stranger = subprocess.Popen([sys.executable, str(WORKER), "sleep"], start_new_session=True)
    try:
        up(fleet.spec, fleet.host)
        fleet.set_version("v2")
        roll(fleet.spec, fleet.host, settle_s=0.1)
        down(fleet.spec)
        assert stranger.poll() is None
        assert not fleet.alive("w-1")
    finally:
        stranger.kill()
        stranger.wait()


def test_a_corrupt_state_file_raises_and_signals_nothing(make_fleet: Make) -> None:
    fleet = make_fleet(count=1)
    up(fleet.spec, fleet.host)
    pid = fleet.pid("w-1")
    path_of(fleet.spec, "w-1").write_text('{"pid": 1, "start": ""}')
    with pytest.raises(StateError):
        down(fleet.spec)
    assert alive(pid, None)
    path_of(fleet.spec, "w-1").unlink()
    down(fleet.spec)  # nothing on disk is ours: nothing signalled
    assert alive(pid, None)
    assert stop_pid(pid, proc_start(pid), grace=2) == ()


@pytest.mark.parametrize("parallel", [1, 2, 8])
def test_roll_never_leaves_a_lane_without_a_live_replica(make_fleet: Make, parallel: int) -> None:
    fleet = make_fleet(count=2)
    up(fleet.spec, fleet.host)
    old = {n: fleet.pid(n) for n in ("w-1", "w-2")}
    fleet.set_version("v2")
    snapshots: list[tuple[bool, bool, int, int]] = []

    def sleep(seconds: float) -> None:  # called on every settle poll, with both replicas in whatever state the roll left them
        snapshots.append((fleet.alive("w-1"), fleet.alive("w-2"), fleet.pid("w-1"), fleet.pid("w-2")))
        fleet.clock.sleep(seconds)

    rolled = roll(fleet.spec, Host(environ=fleet.host.environ, clock=fleet.clock, sleep=sleep), parallel=parallel)
    assert [r.name for r in rolled] == ["w-1", "w-2"]
    assert snapshots
    assert all(a or b for a, b, _, _ in snapshots)  # at every poll at least one replica of the lane lives
    # one at a time even when parallel allows more: while w-1 settles, w-2 is still the old process, and the reverse after
    assert any(p1 != old["w-1"] and p2 == old["w-2"] for _, _, p1, p2 in snapshots)
    assert not any(p1 == old["w-1"] and p2 != old["w-2"] for _, _, p1, p2 in snapshots)
    assert {fleet.pid(n) for n in old}.isdisjoint(old.values())
    assert set(states(fleet).values()) == {State.RUNNING}


def test_a_worker_that_ignores_sigterm_is_killed_after_the_timeout(make_fleet: Make) -> None:
    fleet = make_fleet(mode="stubborn", count=1, stop_timeout_s=0.5)
    up(fleet.spec, fleet.host)
    fleet.wait_ready("w-1")
    old = fleet.pid("w-1")
    fleet.set_version("v2")
    t0 = time.monotonic()
    (rolled,) = roll(fleet.spec, fleet.host)
    took = time.monotonic() - t0
    assert 0.4 <= took < 10
    assert rolled.old_pid == old
    assert rolled.new_pid != old
    assert fleet.alive("w-1")
    assert states(fleet) == {"w-1": State.RUNNING}


def test_a_replacement_that_dies_stops_the_roll_and_leaves_the_rest(make_fleet: Make) -> None:
    fleet = make_fleet(count=2)
    up(fleet.spec, fleet.host)
    fleet.wait_ready("w-1")
    fleet.wait_ready("w-2")
    second = fleet.pid("w-2")
    fleet.set_version("v2")
    (fleet.root / "FAIL").write_text("")
    real = Host(environ=fleet.host.environ)
    with pytest.raises(ReplacementDiedError) as err:
        roll(fleet.spec, real, settle_s=1.5)
    assert err.value.replica == "w-1"
    assert fleet.pid("w-2") == second
    assert fleet.alive("w-2")
    assert states(fleet) == {"w-1": State.DEAD, "w-2": State.STALE}


def test_roll_first_restores_a_dead_replica_of_a_lane_it_rolls(make_fleet: Make) -> None:
    fleet = make_fleet(count=2)
    up(fleet.spec, fleet.host)
    dead = read(fleet.spec, "w-2")
    assert dead is not None
    assert stop_pid(dead.pid, dead.start, grace=2) == ()  # w-2 dies by itself; its state file stays
    fleet.set_version("v2")
    seen: list[bool] = []

    def sleep(seconds: float) -> None:
        seen.append(fleet.alive("w-1") or fleet.alive("w-2"))
        fleet.clock.sleep(seconds)

    rolled = roll(fleet.spec, Host(environ=fleet.host.environ, clock=fleet.clock, sleep=sleep))
    assert [r.name for r in rolled] == ["w-1"]
    assert fleet.alive("w-2")  # started before w-1 was stopped, so the lane never held zero
    assert seen
    assert all(seen)
    assert set(states(fleet).values()) == {State.RUNNING}  # w-2 came back on the current version, w-1 was rolled


def test_roll_names_restarts_even_a_current_replica(make_fleet: Make) -> None:
    fleet = make_fleet(count=2)
    up(fleet.spec, fleet.host)
    keep, old = fleet.pid("w-1"), fleet.pid("w-2")
    (rolled,) = roll(fleet.spec, fleet.host, names=["w-2"])
    assert rolled.old_pid == old
    assert fleet.pid("w-1") == keep
    assert fleet.pid("w-2") != old


def test_roll_with_nothing_stale_does_nothing(make_fleet: Make) -> None:
    fleet = make_fleet(count=2)
    up(fleet.spec, fleet.host)
    assert roll(fleet.spec, fleet.host) == ()


def test_roll_refuses_parallel_below_one(make_fleet: Make) -> None:
    fleet = make_fleet(count=1)
    with pytest.raises(ValueError, match="parallel"):
        roll(fleet.spec, fleet.host, parallel=0)


def test_down_stops_what_is_ours_and_removes_the_state(make_fleet: Make) -> None:
    fleet = make_fleet(count=2)
    up(fleet.spec, fleet.host)
    pid = fleet.pid("w-2")
    (stopped,) = down(fleet.spec, "w-2")
    assert (stopped.name, stopped.pid, stopped.was_running) == ("w-2", pid, True)
    assert states(fleet) == {"w-1": State.RUNNING, "w-2": State.MISSING}
    assert [s.name for s in down(fleet.spec, "w")] == ["w-1"]
    assert set(states(fleet).values()) == {State.MISSING}


def test_down_takes_a_state_file_the_spec_no_longer_lists(make_fleet: Make) -> None:
    fleet = make_fleet(count=2)
    up(fleet.spec, fleet.host)
    shrunk = load_spec(write_spec(fleet.root, count=1))
    rows = {r.name: r.state for r in status(shrunk, fleet.host)}
    assert rows == {"w-1": State.RUNNING, "w-2": State.ORPHAN}
    assert [s.name for s in down(shrunk, "w-2")] == ["w-2"]


def test_down_of_an_unknown_name_raises(make_fleet: Make) -> None:
    fleet = make_fleet(count=1)
    with pytest.raises(UnknownNameError):
        down(fleet.spec, "nope")


def test_workers_get_index_count_env_and_argument_placeholders(make_fleet: Make) -> None:
    fleet = make_fleet(mode="env", count=2, args=("--shard", "{index}/{count}"), extra='env = { EXTRA = "x1" }\nenv_pass = ["PASSED_*"]')
    host = Host(environ={**os.environ, "CLAUDE_CODE_TEST_LEAK": "1", "PASSED_ON": "p1"}, clock=fleet.clock, sleep=fleet.clock.sleep)
    up(fleet.spec, host)
    fleet.wait_ready("w-2")
    text = "\n".join(logs(fleet.spec, "w-2"))
    assert "index 2 count 2 argv ['--shard', '2/2']" in text
    assert "extra x1 leak None passed p1" in text  # only the allowlist and the spec's own env reach the worker


def test_logs_tail_and_ambiguous_name(make_fleet: Make) -> None:
    fleet = make_fleet(count=2)
    up(fleet.spec, fleet.host)
    fleet.wait_ready("w-1")
    assert logs(fleet.spec, "w-1") == ("ready",)
    assert logs(fleet.spec, "w-1", 0) == ()
    with pytest.raises(UnknownNameError):
        logs(fleet.spec, "w")


def test_a_second_mutating_verb_is_refused_while_one_runs(make_fleet: Make) -> None:
    fleet = make_fleet(count=1)
    with _locked(fleet.spec), pytest.raises(BusyError):
        up(fleet.spec, fleet.host)


def run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "any_supervise", *args], cwd=cwd, capture_output=True, text=True, timeout=60, check=False)


def test_the_launch_call_returns_promptly_even_if_the_child_holds_stdout(make_fleet: Make) -> None:
    fleet = make_fleet(mode="chatty", count=2)
    t0 = time.monotonic()
    done = run_cli("up", str(fleet.root / "fleet.toml"), cwd=fleet.root)  # capture_output reads to EOF: it would hang on a held pipe
    assert done.returncode == 0, done.stderr
    assert time.monotonic() - t0 < 20
    assert "2 started" in done.stdout
    assert fleet.alive("w-1")
    assert run_cli("up", str(fleet.root / "fleet.toml"), cwd=fleet.root).stdout.endswith("0 started, 2 already running\n")


def test_the_cli_status_exit_code_and_json(make_fleet: Make) -> None:
    fleet = make_fleet(count=2)
    spec = str(fleet.root / "fleet.toml")
    assert run_cli("status", spec, cwd=fleet.root).returncode == 1  # missing
    assert run_cli("up", spec, cwd=fleet.root).returncode == 0
    ok = run_cli("status", spec, "--json", cwd=fleet.root)
    assert ok.returncode == 0
    assert json.loads(ok.stdout)["ok"] is True
    fleet.set_version("v2")
    stale = run_cli("status", spec, "--json", cwd=fleet.root)
    assert stale.returncode == 1
    assert {r["state"] for r in json.loads(stale.stdout)["replicas"]} == {"stale"}
    assert "STALE" in run_cli("status", spec, cwd=fleet.root).stdout
    assert run_cli("roll", spec, "--settle", "0.2", cwd=fleet.root).returncode == 0
    assert run_cli("status", spec, cwd=fleet.root).returncode == 0
    assert "ready" in run_cli("logs", spec, "w-1", cwd=fleet.root).stdout
    assert run_cli("down", spec, cwd=fleet.root).returncode == 0
    assert run_cli("down", spec, "nope", cwd=fleet.root).returncode == 2
