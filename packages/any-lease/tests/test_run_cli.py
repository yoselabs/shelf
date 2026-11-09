"""``python -m any_lease run``: a unit held for a command, nesting, signals, exit codes."""

from __future__ import annotations

import contextlib
import signal
import subprocess
import sys
import textwrap
import time
from typing import TYPE_CHECKING

from any_lease import Leases

if TYPE_CHECKING:
    from pathlib import Path


def _run(root: Path, name: str, limit: int, label: str, *command: str, **kw: object) -> subprocess.Popen[str]:
    argv = [sys.executable, "-m", "any_lease", "run", "--root", str(root), "--poll", "0.02", name, str(limit), label, "--", *command]
    return subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **kw)  # type: ignore[arg-type]


def _wait_held(root: Path) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        with contextlib.suppress(ValueError):  # not declared until the wrapper's first call
            if Leases(root).holders("unity"):
                return
        time.sleep(0.02)


def test_exit_code_of_the_command_is_returned_and_the_unit_is_held_meanwhile(tmp_path: Path) -> None:
    root = tmp_path / "locks"
    probe = "import sys; sys.exit(3)"
    proc = _run(root, "unity", 1, "job", sys.executable, "-c", probe)
    assert proc.wait(timeout=30) == 3
    assert Leases(root).holders("unity") == ()  # released when the wrapper ended

    sleeper = _run(root, "unity", 1, "job", sys.executable, "-c", "import time; time.sleep(60)")
    _wait_held(root)
    [only] = Leases(root).holders("unity")
    assert only.holder is not None
    assert (only.holder.label, only.holder.pid, "cwd" in only.holder.meta) == ("job", sleeper.pid, True)
    sleeper.send_signal(signal.SIGTERM)
    sleeper.wait(timeout=15)


def test_sigterm_reaches_the_command_and_the_exit_code_says_so(tmp_path: Path) -> None:
    root = tmp_path / "locks"
    script = textwrap.dedent(
        """
        import os, signal, sys, time
        # A handler can interrupt readiness while stdout holds its buffered-writer lock.
        signal.signal(signal.SIGTERM, lambda *_: (os.write(1, b"got term\\n"), sys.exit(7)))
        print("ready", flush=True)
        time.sleep(60)
        """
    )
    proc = _run(root, "unity", 1, "job", sys.executable, "-c", script)
    assert proc.stdout is not None
    assert proc.stdout.readline().strip() == "ready"
    proc.send_signal(signal.SIGTERM)
    out, err = proc.communicate(timeout=15)
    assert proc.returncode == 7, (out, err)
    assert "got term" in out
    assert not err
    assert Leases(root).holders("unity") == ()


def test_a_nested_run_of_a_held_name_runs_without_waiting(tmp_path: Path) -> None:
    root = tmp_path / "locks"
    inner = [
        sys.executable,
        "-m",
        "any_lease",
        "run",
        "--root",
        str(root),
        "unity",
        "1",
        "inner",
        "--",
        sys.executable,
        "-c",
        "print('inner ran')",
    ]
    proc = _run(root, "unity", 1, "outer", *inner)
    out, _ = proc.communicate(timeout=30)  # a nested run that tried for a second unit would wait forever
    assert proc.returncode == 0
    assert "inner ran" in out


def test_a_second_run_waits_for_the_first_and_says_who_it_waits_for(tmp_path: Path) -> None:
    root, go = tmp_path / "locks", tmp_path / "go"
    # The first holds until the test says so, so the second always finds the unit taken, however loaded the machine is.
    hold = f"import pathlib, time\nwhile not pathlib.Path({str(go)!r}).exists():\n    time.sleep(0.02)"
    first = _run(root, "unity", 1, "first", sys.executable, "-c", hold)
    _wait_held(root)
    second = _run(root, "unity", 1, "second", sys.executable, "-c", "print('second ran')")
    assert second.stderr is not None
    assert "second waits for unity (1 busy: first)" in second.stderr.readline()
    go.touch()
    out, _ = second.communicate(timeout=30)
    assert second.returncode == 0
    assert "second ran" in out
    first.wait(timeout=30)
