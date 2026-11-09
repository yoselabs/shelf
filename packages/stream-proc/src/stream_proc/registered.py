"""Register a real child before permitting target execution in that same process."""

from __future__ import annotations

import contextlib
import json
import math
import os
import select
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from stream_proc.hold import TermHold, popen_held
from stream_proc.owned import IdentityUnavailableError, OwnedProcess, inspect_process

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

MAX_FRAME = 8 * 1024 * 1024


class RegisteredStartUncertainError(RuntimeError):
    """Permission transmission began; the registered workload may have executed."""

    def __init__(self, identity: OwnedProcess, *, leader_reaped: bool) -> None:
        super().__init__("Registered target may have executed; leader cleanup is not whole-workload stop proof")
        self.identity = identity
        self.leader_reaped = leader_reaped


def _bootstrap(
    control: int,
    status: int,
    timeout: float,
    *,
    cwd: str | os.PathLike[str] | None,
    env: Mapping[str, str],
    stderr: int,
    start_new_session: bool,
) -> tuple[subprocess.Popen[bytes], TermHold]:
    return popen_held(
        [sys.executable, "-I", "-S", str(Path(__file__).with_name("_exec_gate.py")), str(control), str(status), str(timeout)],
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr,
        start_new_session=start_new_session,
        pass_fds=(control, status),
    )


def _cleanup(child: subprocess.Popen[bytes]) -> None:
    """Only a freshly owned Popen; no recovered PID or inferred process group."""
    try:
        child.wait(timeout=0.2)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=2)
    finally:
        for stream in (child.stdin, child.stdout, child.stderr):
            if stream is not None:
                stream.close()


def _send(fd: int, payload: bytes, deadline: float) -> None:
    os.set_blocking(fd, False)
    pending = memoryview(payload)
    while pending:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([], [fd], [], remaining)[1]:
            raise TimeoutError
        with contextlib.suppress(BlockingIOError):
            pending = pending[os.write(fd, pending) :]


def _ready(fd: int, deadline: float) -> None:
    remaining = deadline - time.monotonic()
    if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
        raise TimeoutError
    if os.read(fd, 1) != b"R":
        msg = "Isolated process bootstrap failed before registration"
        raise RuntimeError(msg)


def _exec_status(fd: int, deadline: float) -> int | None:
    data = bytearray()
    while len(data) < 4:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
            raise TimeoutError
        chunk = os.read(fd, 4 - len(data))
        if not chunk:
            if not data:
                return None
            msg = "Incomplete bootstrap startup status"
            raise RuntimeError(msg)
        data.extend(chunk)
    return int.from_bytes(data, "big")


def _identity(child: subprocess.Popen[bytes]) -> OwnedProcess:
    observation = inspect_process(child.pid)
    if observation.kind != "matching" or observation.identity is None:
        msg = "Cannot establish complete boot-aware identity before target execution"
        raise IdentityUnavailableError(msg)
    return observation.identity


def _startup_error(number: int, executable: str) -> None:
    raise OSError(number, os.strerror(number), executable)


def _abort(
    child: subprocess.Popen[bytes] | None,
    identity: OwnedProcess | None,
    error: BaseException,
    *,
    permission_possible: bool,
) -> None:
    try:
        if child is not None:
            _cleanup(child)
    except BaseException as cleanup_error:
        if permission_possible and identity is not None:
            raise RegisteredStartUncertainError(identity, leader_reaped=False) from cleanup_error
        raise
    if permission_possible and identity is not None:
        raise RegisteredStartUncertainError(identity, leader_reaped=True) from error


def popen_registered(
    argv: Sequence[str],
    *,
    registered: Callable[[OwnedProcess], None],
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    stderr: int = subprocess.PIPE,
    start_new_session: bool = True,
    registration_timeout: float = 5.0,
) -> tuple[subprocess.Popen[bytes], OwnedProcess]:
    """Spawn with piped stdin/stdout; callback must durably register before returning.

    The isolated child exits without target exec on lost/invalid permission. Failure
    cleans up the freshly owned child. Successful return means registered permission,
    not proof that target code ran or that a later stopped leader has no descendants.
    The callback must be bounded by its owning persistence operation. Errors after
    permission transmission begins raise RegisteredStartUncertainError with the
    registered identity; a reaped leader does not establish whole-workload stop.
    """
    if not argv or registration_timeout <= 0 or not math.isfinite(registration_timeout):
        msg = "Nonempty argv and a finite positive registration timeout are required"
        raise ValueError(msg)
    target_env = dict(os.environ if env is None else env)
    raw = json.dumps({"permit": "exec", "argv": list(argv), "env": target_env}).encode("utf-8")
    if len(raw) > MAX_FRAME:
        msg = "Registered invocation exceeds the private frame limit"
        raise ValueError(msg)
    control_read = control_write = status_read = status_write = -1
    child: subprocess.Popen[bytes] | None = None
    identity: OwnedProcess | None = None
    permission_possible = False
    deadline = time.monotonic() + registration_timeout
    try:
        control_read, control_write = os.pipe()
        status_read, status_write = os.pipe()
        child, hold = _bootstrap(
            control_read,
            status_write,
            registration_timeout,
            cwd=cwd,
            env=target_env,
            stderr=stderr,
            start_new_session=start_new_session,
        )
        os.close(control_read)
        control_read = -1
        os.close(status_write)
        status_write = -1
        hold.replay()
        _ready(status_read, deadline)
        identity = _identity(child)
        registered(identity)
        permission_possible = True
        _send(control_write, struct.pack("!I", len(raw)) + raw, deadline)
        os.close(control_write)
        control_write = -1
        number = _exec_status(status_read, deadline)
        if number is not None:
            permission_possible = False
            _startup_error(number, argv[0])
    except BaseException as error:
        if control_write >= 0:
            os.close(control_write)
            control_write = -1
        _abort(child, identity, error, permission_possible=permission_possible)
        raise
    else:
        return child, identity
    finally:
        for fd in (control_read, control_write, status_read, status_write):
            if fd >= 0:
                os.close(fd)
