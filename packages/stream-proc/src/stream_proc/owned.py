"""Boot-aware process identity, read through the process table (`stream_proc.proctable`), which owns the OS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from stream_proc import proctable


@dataclass(frozen=True, slots=True)
class OwnedProcess:
    """PID/start/boot identify a process; pgid is observed mutable metadata."""

    pid: int
    pgid: int
    start: str
    boot: str


@dataclass(frozen=True, slots=True)
class ProcessObservation:
    kind: Literal["matching", "gone", "different_process", "unknown"]
    identity: OwnedProcess | None = None


class IdentityUnavailableError(RuntimeError):
    """The native identity could not be established; execution is not permitted."""


def inspect_process(pid: int) -> ProcessObservation:
    """Read a complete identity; an unreadable record is never known absence."""
    boot = proctable.boot_id()
    if boot is None:
        return ProcessObservation("unknown")
    row = proctable.inspect(pid)
    if isinstance(row, str):
        return ProcessObservation(row)
    if proctable.boot_id() != boot:
        return ProcessObservation("unknown")
    if row.state.startswith(("Z", "X")):
        return ProcessObservation("gone")
    return ProcessObservation("matching", OwnedProcess(row.pid, row.pgid, row.start, boot))


def observe_owned(identity: OwnedProcess) -> ProcessObservation:
    """Match immutable identity, retaining current group metadata, not group ownership proof."""
    boot = proctable.boot_id()
    if boot is None:
        return ProcessObservation("unknown")
    if boot != identity.boot:
        return ProcessObservation("different_process")
    observation = inspect_process(identity.pid)
    current = observation.identity
    if (
        observation.kind == "matching"
        and current is not None
        and (current.pid, current.start, current.boot) != (identity.pid, identity.start, identity.boot)
    ):
        return ProcessObservation("different_process", current)
    return observation
