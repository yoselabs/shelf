"""process-lock's waiting, stale-break, record and non-reentrant contract, stated as Gherkin."""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest
from process_lock import Holder, LockHeldError, ProcessLock, Waiting, held, holder
from pytest_bdd import given, parsers, scenarios, then, when

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

scenarios("features")


@dataclass
class World:
    root: Path
    locks: list[ProcessLock] = field(default_factory=list[ProcessLock])
    fds: list[int] = field(default_factory=list[int])
    seen: list[Waiting] = field(default_factory=list[Waiting])
    refusal: LockHeldError | None = None
    threads: list[threading.Thread] = field(default_factory=list[threading.Thread])


@pytest.fixture
def world(tmp_path: Path) -> Iterator[World]:
    w = World(root=tmp_path)
    yield w
    for t in w.threads:
        t.join(timeout=10)
    for lock in w.locks:
        lock.release()
    for fd in w.fds:
        os.close(fd)
    assert not held()


def _dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait(timeout=10)
    return proc.pid


def _foreign_lock(world: World, name: str, record: dict[str, object]) -> None:
    """A lock on a second descriptor (flock conflicts even in-process) whose record we choose."""
    fd = os.open(world.root / name, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    os.write(fd, json.dumps(record).encode())
    world.fds.append(fd)


@given(parsers.parse('a lock on "{name}" held by another thread for {secs:g} seconds'))
def _held_by_thread(world: World, name: str, secs: float) -> None:
    ready = threading.Event()

    def run() -> None:
        lock = ProcessLock.acquire(world.root / name, reentrant=False)
        ready.set()
        time.sleep(secs)
        lock.release()

    thread = threading.Thread(target=run)
    thread.start()
    world.threads.append(thread)
    assert ready.wait(timeout=10)


@given(parsers.parse('a lock on "{name}" whose record names a dead process'))
def _dead_record(world: World, name: str) -> None:
    _foreign_lock(world, name, {"pid": _dead_pid(), "start": "1", "created": 1.0})


@given(parsers.parse('a lock on "{name}" whose record names my pid with another start time'))
def _reused_record(world: World, name: str) -> None:
    _foreign_lock(world, name, {"pid": os.getppid(), "start": "not-the-start-time", "created": 1.0})


@given("the record is read as stale")
def _stale(world: World) -> None:
    record = holder(world.root / "a.lock")
    assert record is not None
    assert record.is_stale()


@given(parsers.parse('I hold "{name}" with label "{label}" and meta {meta}'))
def _hold_labelled(world: World, name: str, label: str, meta: str) -> None:
    world.locks.append(ProcessLock.acquire(world.root / name, label=label, meta=json.loads(meta)))


@given(parsers.parse('I hold "{name}" non-reentrantly'))
def _hold_non_reentrant(world: World, name: str) -> None:
    world.locks.append(ProcessLock.acquire(world.root / name, reentrant=False))


@given(parsers.parse("I release it after {secs:g} seconds"))
def _release_later(world: World, secs: float) -> None:
    lock = world.locks[-1]
    thread = threading.Timer(secs, lock.release)
    thread.start()
    world.threads.append(thread)


def _acquire(world: World, name: str, secs: float, *, reentrant: bool = True, break_stale: bool = True) -> None:
    try:
        world.locks.append(
            ProcessLock.acquire(world.root / name, timeout=secs, on_wait=world.seen.append, reentrant=reentrant, break_stale=break_stale)
        )
    except LockHeldError as exc:
        world.refusal = exc


@when(parsers.parse('I acquire "{name}" waiting up to {secs:g} seconds'))
def _acquire_waiting(world: World, name: str, secs: float) -> None:
    _acquire(world, name, secs)


@when(parsers.parse('I acquire "{name}" without breaking, waiting up to {secs:g} seconds'))
def _acquire_no_break(world: World, name: str, secs: float) -> None:
    _acquire(world, name, secs, break_stale=False)


@when(parsers.parse('I acquire "{name}" non-reentrantly waiting up to {secs:g} seconds'))
def _acquire_non_reentrant(world: World, name: str, secs: float) -> None:
    _acquire(world, name, secs, reentrant=False)


@then(parsers.parse('I hold "{name}"'))
def _i_hold(world: World, name: str) -> None:
    assert world.refusal is None
    assert (world.root / name).resolve() in held()


@then("the waiting callback was called with the holder's pid")
def _callback_saw_holder(world: World) -> None:
    assert world.seen
    assert all(isinstance(w, Waiting) and isinstance(w.holder, Holder) and w.holder.pid == os.getpid() for w in world.seen)
    assert world.seen[-1].elapsed > 0


@then("the acquire is refused naming the holder's pid")
def _refused(world: World) -> None:
    assert world.refusal is not None
    assert world.refusal.pid is not None
    assert world.refusal.holder is not None


@then("the acquire is refused naming my pid")
def _refused_me(world: World) -> None:
    assert world.refusal is not None
    assert world.refusal.pid == os.getpid()


@then(parsers.parse('holder "{name}" shows my pid, label "{label}" and meta {meta}'))
def _holder_shows(world: World, name: str, label: str, meta: str) -> None:
    record = holder(world.root / name)
    assert record is not None
    assert (record.pid, record.label, record.meta) == (os.getpid(), label, json.loads(meta))
    assert record.created > 0
    assert record.start is None or record.start


@then(parsers.parse('holder "{name}" shows my pid'))
def _holder_is_me(world: World, name: str) -> None:
    record = holder(world.root / name)
    assert record is not None
    assert record.pid == os.getpid()
