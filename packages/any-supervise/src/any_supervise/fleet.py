"""The verbs: status, up, roll, down, logs. Every signal goes through an identity check (pid AND process start time)."""

from __future__ import annotations

import contextlib
import dataclasses
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from child_env import build_env
from process_lock import LockHeldError, ProcessLock
from stream_proc import IdentityUnavailableError, alive, capture, spawn_detached, stop_pid

from any_supervise import store
from any_supervise.model import (
    BusyError,
    Record,
    ReplacementDiedError,
    ReplicaStatus,
    Rolled,
    Started,
    StartFailedError,
    State,
    StateError,
    StopFailedError,
    Stopped,
    UnknownNameError,
    VersionProbeError,
)
from any_supervise.spec import STOP_TIMEOUT_S

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Mapping, Sequence

    from any_supervise.model import Replica, Spec

VERSION_TIMEOUT_S = 30.0
_POLL_S = 0.1
_TAIL_BYTES = 262_144


@dataclasses.dataclass(frozen=True)
class Host:
    """What the library takes from outside: the launcher's environment (workers get only what the spec passes on), a clock, a sleep."""

    environ: Mapping[str, str]
    clock: Callable[[], float] = time.time
    sleep: Callable[[float], None] = time.sleep


def current_version(spec: Spec, host: Host) -> str:
    """The code version now: `version_cmd`'s stdout, stripped. Raises `VersionProbeError`."""
    got = capture(spec.version_cmd, cwd=spec.version_cwd, env=build_env(host.environ), timeout=VERSION_TIMEOUT_S)
    version = got.text.strip()
    if got.exit != 0 or not version:
        msg = f"version_cmd {list(spec.version_cmd)} in {spec.version_cwd}: exit {got.exit}, {got.err_text.strip()[:300] or 'no output'}"
        raise VersionProbeError(msg)
    return version


def status(spec: Spec, host: Host) -> tuple[ReplicaStatus, ...]:
    """One row per replica of the spec, then one per state file outside it. Reads only: no lock, no signal."""
    current = current_version(spec, host)
    in_spec = {r.name for r in spec.replicas}
    rows = [_status(spec, r.name, current, listed=True) for r in spec.replicas]
    rows += [_status(spec, name, current, listed=False) for name in store.names(spec) if name not in in_spec]
    return tuple(rows)


def _status(spec: Spec, name: str, current: str, *, listed: bool) -> ReplicaStatus:
    rec = store.read(spec, name)
    if rec is None:
        return ReplicaStatus(name, State.MISSING, None, None, current, None)
    if not alive(rec.pid, rec.start):
        state = State.DEAD
    elif not listed:
        state = State.ORPHAN
    else:
        state = State.RUNNING if rec.version == current else State.STALE
    return ReplicaStatus(name, state, rec.pid, rec.version, current, rec.started_at)


def up(spec: Spec, host: Host) -> tuple[Started, ...]:
    """Start every replica that is missing or dead, detached; one that runs is left alone (stale or not). Idempotent."""
    with _locked(spec):
        version = current_version(spec, host)
        started = [_start(spec, r, version, host) for r in spec.replicas if not _running(spec, r.name)]
        return tuple(Started(s.name, s.pid, s.version) for s in started)


def roll(spec: Spec, host: Host, *, parallel: int = 1, names: Sequence[str] = (), settle_s: float = 3.0) -> tuple[Rolled, ...]:
    """Replace stale replicas (or those `names` select: workers or replicas, stale or not) with ones on the current version.

    Per replica: SIGTERM to the process group after the identity check, SIGKILL after the worker's `stop_timeout_s`, start the
    replacement, and require it alive for `settle_s` before the replica counts as done. At most `parallel` replicas are in
    flight, and never every replica of one worker while it has more than one. The first failure stops the roll: replicas not
    yet started on are left untouched.
    """
    if parallel < 1:
        msg = "parallel must be >= 1"
        raise ValueError(msg)
    with _locked(spec):
        version = current_version(spec, host)
        if names:
            wanted = {r.name for n in names for r in spec.select(n)}
            targets = [r for r in spec.replicas if r.name in wanted]
        else:
            targets = [r for r in spec.replicas if _status(spec, r.name, version, listed=True).state is State.STALE]
        chosen = {r.name for r in targets}
        for r in spec.replicas:  # a lane never goes to zero: its dead or missing replicas come back before any live one is stopped
            if r.worker.name in {t.worker.name for t in targets} and r.name not in chosen and not _running(spec, r.name):
                _start(spec, r, version, host)
        return _roll_all(spec, host, targets, version, parallel=parallel, settle_s=settle_s)


def _roll_all(spec: Spec, host: Host, targets: Sequence[Replica], version: str, *, parallel: int, settle_s: float) -> tuple[Rolled, ...]:
    lanes = {w.name: threading.Semaphore(max(1, w.count - 1)) for w in spec.workers}
    abort = threading.Event()

    def one(replica: Replica) -> Rolled | None:
        with lanes[replica.worker.name]:
            if abort.is_set():
                return None
            try:
                return _replace(spec, host, replica, version, settle_s)
            except BaseException:
                abort.set()
                raise

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        futures = [pool.submit(one, r) for r in targets]
    for future in futures:
        if (error := future.exception()) is not None:
            raise error
    return tuple(r for f in futures if (r := f.result()) is not None)


def _replace(spec: Spec, host: Host, replica: Replica, version: str, settle_s: float) -> Rolled:
    old = _stop(spec, replica.name, replica.worker.stop_timeout_s)
    new = _start(spec, replica, version, host)
    until = host.clock() + settle_s
    while host.clock() < until:
        if not alive(new.pid, new.start):
            raise ReplacementDiedError(replica.name, replica.log)
        host.sleep(_POLL_S)
    if not alive(new.pid, new.start):
        raise ReplacementDiedError(replica.name, replica.log)
    return Rolled(replica.name, old, new.pid, version)


def down(spec: Spec, name: str | None = None) -> tuple[Stopped, ...]:
    """Stop what is ours, gracefully (SIGTERM, then SIGKILL after `stop_timeout_s`), and remove its state file.

    `name` is a worker, a replica, or a state file outside the spec (an orphan); without it every state file. A state file whose
    process is gone is just removed. Every target is attempted; failures are raised together afterwards.
    """
    with _locked(spec):
        timeouts = {r.name: r.worker.stop_timeout_s for r in spec.replicas}
        stopped: list[Stopped] = []
        errors: list[Exception] = []
        for target in _down_names(spec, name):
            try:
                stopped.append(_down_one(spec, target, timeouts.get(target, STOP_TIMEOUT_S)))
            except (StopFailedError, StateError) as exc:
                errors.append(exc)
        if len(errors) == 1:
            raise errors[0]
        if errors:
            msg = "some replicas could not be stopped"
            raise ExceptionGroup(msg, errors)
        return tuple(stopped)


def _down_names(spec: Spec, name: str | None) -> tuple[str, ...]:
    on_disk = store.names(spec)
    if name is None:
        return on_disk
    if name in on_disk and not any(name in {r.name, r.worker.name} for r in spec.replicas):
        return (name,)
    return tuple(r.name for r in spec.select(name) if r.name in on_disk)


def _down_one(spec: Spec, name: str, timeout: float) -> Stopped:
    rec = store.read(spec, name)
    if rec is None:
        msg = f"{name}: state file vanished"
        raise StateError(msg)
    was_running = alive(rec.pid, rec.start)
    _stop(spec, name, timeout)
    store.remove(spec, name)
    return Stopped(name, rec.pid, was_running)


def logs(spec: Spec, name: str, lines: int = 50) -> tuple[str, ...]:
    """The last `lines` lines of one replica's log. A worker name is refused when it has several replicas."""
    replicas = spec.select(name)
    if len(replicas) != 1:
        msg = f"{name!r} names several replicas: {[r.name for r in replicas]}"
        raise UnknownNameError(msg)
    with replicas[0].log.open("rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - _TAIL_BYTES))
        text = f.read().decode("utf-8", errors="replace")  # lossy-ok: display: a log tail shown to a person
    return tuple(text.splitlines()[-lines:]) if lines > 0 else ()


def _running(spec: Spec, name: str) -> bool:
    rec = store.read(spec, name)
    return rec is not None and alive(rec.pid, rec.start)


def _stop(spec: Spec, name: str, timeout: float) -> int | None:
    """Stop `name` if its state file's (pid, start) is still a live process; returns the pid stopped, else None."""
    rec = store.read(spec, name)
    if rec is None or not alive(rec.pid, rec.start):
        return None
    if survivors := stop_pid(rec.pid, rec.start, grace=timeout):
        raise StopFailedError(name, survivors)
    return rec.pid


def _start(spec: Spec, replica: Replica, version: str, host: Host) -> Record:
    env = build_env(
        host.environ,
        allow=replica.worker.env_pass,
        extra={**replica.worker.env, "ANY_SUPERVISE_INDEX": str(replica.index), "ANY_SUPERVISE_COUNT": str(replica.worker.count)},
    )
    try:
        child = spawn_detached(replica.argv, cwd=replica.worker.cwd, env=env, log=replica.log)
    except IdentityUnavailableError as exc:
        msg = f"{replica.name}: {exc}"
        raise StartFailedError(msg) from exc
    record = Record(replica.name, child.pid, child.start, replica.argv, version, host.clock())
    try:
        store.write(spec, record)
    except BaseException:
        # a worker we cannot record is a worker we could never stop later: do not leave it running
        stop_pid(child.pid, child.start, grace=replica.worker.stop_timeout_s)
        raise
    return record


@contextlib.contextmanager
def _locked(spec: Spec) -> Generator[None]:
    """One mutating verb at a time per state folder; a second one raises `BusyError` at once."""
    try:
        lock = ProcessLock.acquire_exclusive(spec.state / ".lock", label="any-supervise")
    except LockHeldError as exc:
        msg = f"another any-supervise verb holds {spec.state}: {exc}"
        raise BusyError(msg) from exc
    try:
        yield
    finally:
        lock.release()
