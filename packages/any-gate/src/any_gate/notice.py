"""The descriptor a gate's notices go to, and the proof a receiver holds that a number is that descriptor.

`GATE_NOTICE_FD` is a descriptor number of the gate's own process. It is inherited by every process below a step, where that number may
be closed or, worse, may name an unrelated pipe (an xdist worker's link to its controller: a notice written there hung a full gate at
91-94% until the idle limit, 2026-11-28). So the gate also announces `GATE_NOTICE_ID` = `dev:ino` of the descriptor, and a receiver writes
only when `fstat(number)` matches it. The number stays a bare number: a shell recipe writes `>&"$GATE_NOTICE_FD"`.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["FD_ENV", "ID_ENV", "announce", "descriptor", "scrub"]

FD_ENV = "GATE_NOTICE_FD"
ID_ENV = "GATE_NOTICE_ID"


def announce(env: Mapping[str, str], fd: int) -> dict[str, str]:
    """`env` plus the number of `fd` and the identity of what it names."""
    info = os.fstat(fd)
    return {**env, FD_ENV: str(fd), ID_ENV: f"{info.st_dev}:{info.st_ino}"}


def descriptor(env: Mapping[str, str]) -> int | None:
    """The descriptor `env` announces, only while it is still the one announced (same device and inode); else None."""
    number, token = env.get(FD_ENV, ""), env.get(ID_ENV, "")
    if not number.isdigit() or not token:
        return None
    try:
        info = os.fstat(int(number))
    except OSError:
        return None
    return int(number) if token == f"{info.st_dev}:{info.st_ino}" else None


def scrub(env: Mapping[str, str]) -> dict[str, str]:
    """`env` without the notice descriptor: for a tree that must not write to the gate's terminal."""
    return {name: value for name, value in env.items() if name not in (FD_ENV, ID_ENV)}
