"""Count the file opens and process starts of each gate step (`any-gate steps --opens`).

Why: on a machine with a file scanner (Microsoft Defender adds about 20 ms to each open) a gate's cost is its file opens and process
starts, not its CPU. This says which step spends them.

How: every step runs with a `sitecustomize` first on `PYTHONPATH`; each Python process it starts installs a `sys.addaudithook` that
counts the `open` event (a path, never a file descriptor; imports count, they go through `io.open_code`) and the events that start a
process (`subprocess.Popen`, `os.posix_spawn`, `os.fork`, `os.exec*`, `os.system`), and appends one line to the step's file at exit.
No root, no tracing tool: it works on macOS as it is.

What it does not see: opens by a process that is not Python (ruff, just, git, uv), and a Python started with `-I` (isolated mode ignores
`PYTHONPATH`) or killed by a signal before it exits. The numbers are a floor, comparable between runs of one gate, not a total.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

_HOOK = """\
import atexit, os, sys

_log = os.environ.get("GATE_OPENS_LOG")
_n = {"open": 0, "spawn": 0}
_SPAWN = {"subprocess.Popen", "os.posix_spawn", "os.fork", "os.system"}


def _hook(event, args):
    if event == "open":
        if isinstance(args[0], (str, bytes, os.PathLike)):
            _n["open"] += 1
    elif event in _SPAWN or event.startswith("os.exec"):
        _n["spawn"] += 1


def _write():
    try:
        with open(_log, "a") as out:
            out.write(f"{os.getpid()} {_n['open']} {_n['spawn']}\\n")
    except OSError:
        pass


if _log:
    sys.addaudithook(_hook)
    atexit.register(_write)
"""


@dataclass(frozen=True)
class Opens:
    """One step's counts: file opens and process starts seen from Python, and how many Python processes reported."""

    step: str
    opens: int
    spawns: int
    pythons: int


def prepare(folder: Path) -> Path:
    """Write the hook into `folder`; the path to put first on `PYTHONPATH`."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "sitecustomize.py").write_text(_HOOK, encoding="utf-8")
    return folder


def env_for(step: str, folder: Path, env: Mapping[str, str]) -> dict[str, str]:
    """`env` for `step`: the hook on `PYTHONPATH`, the step's own file in `GATE_OPENS_LOG`."""
    existing = env.get("PYTHONPATH", "")
    return {
        **env,
        "PYTHONPATH": f"{folder}{os.pathsep}{existing}" if existing else str(folder),
        "GATE_OPENS_LOG": str(folder / f"{step}.opens"),
    }


def collect(folder: Path, steps: Sequence[str]) -> list[Opens]:
    """Each step's counts, most opens first; a step no Python process reported for is listed with zeros."""
    found = []
    for step in steps:
        log = folder / f"{step}.opens"
        rows: list[list[str]] = [line.split() for line in log.read_text(encoding="utf-8").splitlines()] if log.is_file() else []
        counts = [(int(r[1]), int(r[2])) for r in rows if len(r) == 3 and r[1].isdigit() and r[2].isdigit()]
        found.append(Opens(step, sum(o for o, _ in counts), sum(s for _, s in counts), len(counts)))
    return sorted(found, key=lambda o: (-o.opens, o.step))


def lines(counts: Sequence[Opens], *, top: int = 5) -> list[str]:
    """The report lines: the `top` steps by opens, then what the numbers do not cover."""
    shown = [f"gate opens: {c.step} {c.opens} opens · {c.spawns} spawns · {c.pythons} python procs" for c in counts[:top]]
    return [*shown, "gate opens: python processes only (no `-I`, none killed by a signal); ruff, git, uv and just are not counted"]
