"""Boot-aware process identity from the owning native process reader."""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID

from stream_proc import procfs, procmac


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


def boot_id() -> str | None:
    """The native boot UUID, or unknown. Never substitute wall time or PID."""
    try:
        if sys.platform == "darwin":
            lib = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
            query = lib.sysctlbyname
            query.argtypes = (ctypes.c_char_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p, ctypes.c_size_t)
            query.restype = ctypes.c_int
            buf = ctypes.create_string_buffer(37)
            size = ctypes.c_size_t(len(buf))
            if query(b"kern.bootsessionuuid", buf, ctypes.byref(size), None, 0) != 0 or size.value != len(buf):
                return None
            text = buf.value.decode("ascii")
        elif sys.platform == "linux":
            text = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
        else:
            return None
        return str(UUID(text))
    except (OSError, ValueError, UnicodeError, AttributeError):
        return None


def inspect_process(pid: int) -> ProcessObservation:
    """Read a complete identity; an unreadable record is never known absence."""
    boot = boot_id()
    if boot is None:
        return ProcessObservation("unknown")
    row = procmac.inspect(pid) if sys.platform == "darwin" else procfs.inspect(pid)
    if isinstance(row, str):
        return ProcessObservation(row)
    if boot_id() != boot:
        return ProcessObservation("unknown")
    if row.state.startswith(("Z", "X")):
        return ProcessObservation("gone")
    return ProcessObservation("matching", OwnedProcess(row.pid, row.pgid, row.start, boot))


def observe_owned(identity: OwnedProcess) -> ProcessObservation:
    """Match immutable identity, retaining current group metadata, not group ownership proof."""
    boot = boot_id()
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
