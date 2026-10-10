"""Run a child once and read back one JSON result.

The parent side is :func:`call`: arguments are a JSON object piped over stdin (checked and
size-capped before anything spawns), the child runs under ``setrlimit`` caps applied
between fork and exec, a timeout kills it, and the last marked line of its stdout is
parsed back. The child side is :func:`read_args` and :func:`emit`. The marker is spelled
once, here, so the two ends cannot drift.

POSIX only: the limits ride on ``preexec_fn``.
"""

from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

#: Prefix of the one stdout line that carries the child's JSON result.
RESULT_MARKER = "__ANY_PROC_RESULT__"

#: The default cap on the serialized arguments: generous for a request, bounds a hostile one.
DEFAULT_MAX_ARGS_BYTES = 64 * 1024


class ArgsError(ValueError):
    """Arguments that cannot cross to the child: not a JSON object, not serializable, or
    over the size cap. Raised before anything spawns, or by :func:`read_args` in the child."""


@dataclass(frozen=True)
class Limits:
    """OS limits for the child. ``None`` leaves that limit as inherited.

    ``process_headroom`` is headroom, not a total: ``RLIMIT_NPROC`` counts every process
    (macOS) or thread (Linux) of the user, not the child's own, so the cap is the user's
    count at spawn plus this. A fixed total fails any fork on a busy machine. When the
    count cannot be read the limit is left as inherited.
    """

    memory_bytes: int | None = None
    file_size_bytes: int | None = None
    process_headroom: int | None = None


@dataclass(frozen=True)
class Outcome:
    """What one run produced.

    ``result`` is the JSON object on the last marked line, or ``None`` when the child wrote
    none (it crashed, was killed by a limit, or timed out). ``returncode`` is ``None`` on a
    timeout.
    """

    result: dict[str, Any] | None
    returncode: int | None
    stderr: str
    duration_ms: int
    timed_out: bool = False


def encode_args(args: Mapping[str, Any] | None, *, max_bytes: int = DEFAULT_MAX_ARGS_BYTES) -> str | None:
    """The JSON to pipe to the child, or ``None`` for no arguments.

    Raises :class:`ArgsError` for a non-object, an unserializable value, or a payload over
    ``max_bytes`` once encoded as UTF-8.
    """
    if args is None:
        return None
    if not isinstance(args, dict):
        msg = f"arguments must be a JSON object, got {type(args).__name__}"
        raise ArgsError(msg)
    try:
        encoded = json.dumps(args)
    except (TypeError, ValueError) as exc:
        msg = "arguments are not JSON-serializable"
        raise ArgsError(msg) from exc
    if len(encoded.encode("utf-8")) > max_bytes:
        msg = f"arguments exceed the {max_bytes}-byte cap"
        raise ArgsError(msg)
    return encoded


def user_task_count() -> int | None:
    """What ``RLIMIT_NPROC`` counts for this user now: threads on Linux, processes on macOS.

    ``None`` when it cannot be read.
    """
    uid = os.getuid()
    proc = Path("/proc")
    if proc.is_dir():
        count = 0
        for entry in proc.iterdir():
            if not entry.name.isdigit():
                continue
            try:
                if entry.stat().st_uid == uid:
                    count += sum(1 for _ in (entry / "task").iterdir())
            except OSError:
                continue
        return count
    try:
        # Absolute path: a launchd job's PATH does not reach /bin tools reliably.
        out = subprocess.run(["/bin/ps", "-U", str(uid), "-o", "pid="], capture_output=True, text=True, check=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return len(out.stdout.split())


def _set_limit(res: int, want: int) -> None:
    # Clamp into [., current hard] so the hard cap is never raised. Best-effort: macOS
    # reports RLIMIT_AS's hard cap as infinite yet refuses a finite one; failing the spawn
    # over that would be worse than running without it. Linux enforces all three.
    try:
        _soft, hard = resource.getrlimit(res)
        target = want if hard == resource.RLIM_INFINITY else min(want, hard)
        resource.setrlimit(res, (target, hard))
    except (ValueError, OSError):
        pass


def _preexec(limits: Limits) -> Callable[[], None]:
    """The ``preexec_fn`` that applies ``limits`` in the forked child.

    The user's task count is read here, in the parent, before the fork: the closure only
    calls ``setrlimit``, which is async-signal-safe, so it is safe under a threaded parent.
    """
    nproc = None
    if limits.process_headroom is not None:
        running = user_task_count()
        nproc = None if running is None else running + limits.process_headroom

    def _in_child() -> None:  # pragma: no cover - runs in the forked child, not measured here
        if limits.memory_bytes is not None:
            _set_limit(resource.RLIMIT_AS, limits.memory_bytes)
        if limits.file_size_bytes is not None:
            _set_limit(resource.RLIMIT_FSIZE, limits.file_size_bytes)
        if nproc is not None:
            _set_limit(resource.RLIMIT_NPROC, nproc)

    return _in_child


def call(
    argv: Sequence[str],
    *,
    args: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
    cwd: str | os.PathLike[str] | None = None,
    timeout: float | None = None,
    limits: Limits | None = None,
    max_args_bytes: int = DEFAULT_MAX_ARGS_BYTES,
) -> Outcome:
    """Run ``argv`` to completion and parse its marked result line.

    Invalid ``args`` raise :class:`ArgsError` before anything spawns. A timeout kills the
    child and returns ``timed_out=True``; a child that writes no result returns
    ``result=None`` with its return code and stderr. Nothing else is raised for a child's
    own failure.
    """
    stdin_json = encode_args(args, max_bytes=max_args_bytes)
    preexec_fn = _preexec(limits) if limits is not None else None
    started = time.monotonic()
    try:
        proc = subprocess.run(
            list(argv),
            check=False,
            capture_output=True,
            text=True,
            env=dict(env) if env is not None else None,
            cwd=cwd,
            timeout=timeout,
            input=stdin_json,
            # No arguments is an empty stdin, never the parent's: a child that reads an
            # inherited terminal waits on it until the timeout.
            stdin=subprocess.DEVNULL if stdin_json is None else None,
            preexec_fn=preexec_fn,  # setrlimit only, async-signal-safe; see _preexec
        )
    except subprocess.TimeoutExpired as exc:
        stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return Outcome(result=None, returncode=None, stderr=stderr, duration_ms=_ms_since(started), timed_out=True)
    return Outcome(result=parse_result(proc.stdout), returncode=proc.returncode, stderr=proc.stderr, duration_ms=_ms_since(started))


def _ms_since(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def parse_result(stdout: str) -> dict[str, Any] | None:
    """The JSON object on the last marked line of ``stdout``, or ``None``.

    The last marked line wins, so a child that logs a marker-looking line early is still
    read right. A marked line that is not a JSON object reads as no result.
    """
    for line in reversed(stdout.splitlines()):
        if line.startswith(RESULT_MARKER):
            try:
                parsed = json.loads(line[len(RESULT_MARKER) :].strip())
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else None
    return None


def emit(payload: Mapping[str, Any], stream: TextIO | None = None) -> None:
    """Child side: write ``payload`` as the marked result line, flushed."""
    out = stream if stream is not None else sys.stdout
    out.write(f"{RESULT_MARKER} {json.dumps(dict(payload))}\n")
    out.flush()


def read_args(stream: TextIO | None = None) -> dict[str, Any] | None:
    """Child side: read stdin once and parse it as the arguments.

    Empty or unreadable stdin means no arguments (``None``). Anything else that is not a
    JSON object raises :class:`ArgsError`.
    """
    source = stream if stream is not None else sys.stdin
    try:
        raw = source.read()
    except (OSError, ValueError):
        # A closed or detached stdin, or a harness that captured it: no arguments.
        return None
    if not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = "arguments on stdin are not JSON"
        raise ArgsError(msg) from exc
    if not isinstance(parsed, dict):
        msg = "arguments must be a JSON object"
        raise ArgsError(msg)
    return parsed


__all__ = [
    "DEFAULT_MAX_ARGS_BYTES",
    "RESULT_MARKER",
    "ArgsError",
    "Limits",
    "Outcome",
    "call",
    "emit",
    "encode_args",
    "parse_result",
    "read_args",
    "user_task_count",
]
