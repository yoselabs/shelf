"""The real target cannot run until its process registration is durable."""

from __future__ import annotations

import os
import select
import sys
from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from pathlib import Path

    from any_agent.procs import Worker

import pytest
from stream_proc import RegisteredStartUncertainError, registered

from any_agent import ClaudeHarness, LaunchSpec, NullSink, RunHooks, run


def test_target_waits_for_registration(tmp_path: Path) -> None:
    fifo = tmp_path / "notify"
    os.mkfifo(fifo)
    reader = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
    marker = tmp_path / "executed"
    code = (
        "from pathlib import Path; import os; "
        f"Path({str(marker)!r}).write_text('executed'); "
        f"f=os.open({str(fifo)!r},os.O_WRONLY); os.write(f,b'x'); os.close(f)"
    )

    def registered(_worker: object) -> None:
        readable, _, _ = select.select([reader], [], [], 0.3)
        assert not readable
        assert not marker.exists()

    try:
        spec = LaunchSpec(argv=[sys.executable, "-c", code], env=dict(os.environ), cwd=str(tmp_path), stdin="")
        result = run(ClaudeHarness(), spec, 10, RunHooks(started=registered))
        assert result.rc == 0
        assert marker.read_text() == "executed"
    finally:
        os.close(reader)


@pytest.mark.parametrize("failure", [KeyboardInterrupt, SystemExit])
def test_registration_base_exception_never_executes_target(tmp_path: Path, failure: type[BaseException]) -> None:
    marker = tmp_path / "executed"
    code = f"from pathlib import Path; Path({str(marker)!r}).write_text('executed')"

    def registered(_worker: object) -> None:
        raise failure

    spec = LaunchSpec(argv=[sys.executable, "-c", code], env=dict(os.environ), cwd=str(tmp_path), stdin="")
    with pytest.raises(failure):
        run(ClaudeHarness(), spec, 10, RunHooks(started=registered))
    assert not marker.exists()


def test_live_start_failure_is_still_behind_the_gate(tmp_path: Path) -> None:
    marker = tmp_path / "executed"
    code = f"open({str(marker)!r},'w').write('executed')"

    class FailingSink(NullSink):
        @override
        def started(self, pid: int) -> None:
            raise KeyboardInterrupt

    spec = LaunchSpec(argv=[sys.executable, "-c", code], env=dict(os.environ), cwd=str(tmp_path), stdin="")
    with pytest.raises(KeyboardInterrupt):
        run(ClaudeHarness(), spec, 10, live=FailingSink())
    assert not marker.exists()


def test_postpermit_uncertainty_keeps_the_registered_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workers: list[Worker] = []
    hooks = RunHooks(started=workers.append)

    def lost_status(_fd: int, _deadline: float) -> int | None:
        raise TimeoutError

    monkeypatch.setattr(registered, "_exec_status", lost_status)
    spec = LaunchSpec(argv=[sys.executable, "-c", "pass"], env=dict(os.environ), cwd=str(tmp_path), stdin="")
    with pytest.raises(RegisteredStartUncertainError) as failure:
        run(ClaudeHarness(), spec, 10, hooks)
    assert len(workers) == 1
    identity = failure.value.identity
    assert (identity.pid, identity.pgid, identity.start, identity.boot) == (
        workers[0].pid,
        workers[0].pgid,
        workers[0].start,
        workers[0].boot,
    )
    assert hooks.stops == []  # No whole-workload stop proof was produced.
