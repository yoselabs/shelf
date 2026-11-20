"""Project a supervised agent run into the completion contract."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import threading
import time
from typing import TYPE_CHECKING, Protocol

from anyllm.base import Completion
from anyllm.errors import AnyLLMError

if TYPE_CHECKING:
    import types

    from any_agent import Harness, LaunchSpec

WAIT_AFTER_KILL_S = 30.0  # the supervisor returns once its child is dead; a bound, so a stuck thread cannot hold a cancel forever


class _HasGroup(Protocol):
    @property
    def pgid(self) -> int: ...


class _StartRefusedError(Exception):
    """The awaiting task was cancelled before the child started: do not start it."""


class _Child:
    """The worker's process group, shared between the supervisor thread and the cancelling task."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._worker: _HasGroup | None = None
        self._cancelled = False

    def started(self, worker: _HasGroup) -> None:
        with self._lock:
            if self._cancelled:
                raise _StartRefusedError
            self._worker = worker

    def kill(self) -> None:
        """Mark cancelled and kill the child's whole group, if it started (else the started hook refuses it)."""
        with self._lock:
            self._cancelled = True
            worker = self._worker
        if worker is not None and worker.pgid > 1:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(worker.pgid, signal.SIGKILL)


async def complete_run(agent: types.ModuleType, harness: Harness, spec: LaunchSpec, model: str) -> Completion:
    """Run the synchronous supervisor off the event loop; CLI errors never permit API fallback."""
    t0 = time.perf_counter()
    child = _Child()
    # A cancelled await does not stop a thread: kill the child's group, so the supervisor returns and the thread ends.
    thread = asyncio.ensure_future(asyncio.to_thread(agent.run, harness, spec, 0, agent.RunHooks(started=child.started)))
    try:
        result = await asyncio.shield(thread)
    except asyncio.CancelledError:
        if not thread.done():  # a finished run's group id may belong to someone else by now
            child.kill()
            await asyncio.wait({thread}, timeout=WAIT_AFTER_KILL_S)
        if thread.done() and not thread.cancelled():
            thread.exception()  # retrieved: the cancel is what the caller sees
        raise
    except OSError as exc:
        msg = f"failed to invoke {harness.kind} CLI: {exc}"
        raise AnyLLMError(msg, retryable=False) from exc
    finally:
        if thread.done():
            harness.cleanup()  # the sealed launch's empty directory
    summary = result.summary
    outcome = agent.classify(
        summary.rc,
        summary.vendor,
        summary.stderr,
        result.timed_out,
        summary.work,
        structured=summary.facts,
    )
    if outcome is not None or summary.rc != 0 or result.rc != 0 or result.stop not in (None, "answer"):
        detail = outcome.detail if outcome else summary.stderr or str(result.stop or "run failed")
        msg = f"{harness.kind} CLI exited {result.rc}: {detail[:300]}"
        raise AnyLLMError(
            msg,
            retryable=False,
            hint=f"check `{harness.kind}` auth / subscription credit; this adapter never falls back to the billed API",
        )
    if not summary.text:
        msg = f"{harness.kind} CLI returned no completion"
        raise AnyLLMError(msg, retryable=False)
    tokens = summary.res.get("tokens") or {}
    return Completion(
        text=summary.text,
        model=model,
        prompt_tokens=int(tokens.get("in") or 0),
        completion_tokens=int(tokens.get("out") or 0),
        cost_usd=summary.cost,
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )
