"""Run pytest in stages: the parallel tests, then the `serial` ones alone, then the `quarantine` ones that can never block.

Each stage is one pytest process run under a wall and an idle limit; a limit stops its whole process tree (stream-proc). pytest
exits 5 when a stage's marker selects nothing: that is not a failure. A repo declares the `serial` and `quarantine` markers itself.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from stream_proc import run as run_process

from any_gate.markers_plugin import PREFIX

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path

__all__ = ["Outcome", "Stage", "run_tests"]

_NO_TESTS = 5
# name, marker expression, runs alone (no worker pool)
_STAGES: tuple[tuple[str, str, bool], ...] = (
    ("parallel", "not serial and not quarantine", False),
    ("serial", "serial and not quarantine", True),
    ("quarantine", "quarantine", True),
)


@dataclass(frozen=True)
class Stage:
    """One pytest process: its marker stage, exit code, wall seconds, and why we stopped it (`wall` or `idle`), if we did."""

    name: str
    returncode: int | None
    seconds: float
    stopped: Literal["wall", "idle", "stopped"] | None


@dataclass(frozen=True)
class Outcome:
    """How the stages went. `ok` ignores the quarantine stage; `quarantined_failed` reports it."""

    stages: tuple[Stage, ...]

    @property
    def ok(self) -> bool:
        return all(_ok(stage) for stage in self.stages if stage.name != "quarantine")

    @property
    def quarantined_failed(self) -> bool:
        return any(not _ok(stage) for stage in self.stages if stage.name == "quarantine")


def _ok(stage: Stage) -> bool:
    return stage.stopped is None and stage.returncode in (0, _NO_TESTS)


def _lanes(paths: Sequence[str], *, cwd: Path, python: str, wall: float, idle: float, env: Mapping[str, str] | None) -> set[str]:
    """The lanes (`serial`, `quarantine`) some selected test is marked for: one collection, so an empty lane costs no process."""
    seen: list[str] = []
    cmd = [python, "-m", "pytest", "--collect-only", "-q", "-p", "any_gate.markers_plugin", "-p", "no:cacheprovider", *paths]

    def hear(line: str) -> None:
        if line.startswith(PREFIX):
            seen.extend(line.removeprefix(PREFIX).split())

    run_process(cmd, cwd=cwd, env=env, on_stdout=hear, timeout=wall, idle=idle)
    return set(seen)


def run_tests(
    paths: Sequence[str],
    *,
    cwd: Path,
    workers: int = 1,
    python: str = sys.executable,
    wall: float = 3600.0,
    idle: float = 600.0,
    env: Mapping[str, str] | None = None,
    on_output: Callable[[str], None] | None = None,
    extra: Sequence[str] = (),
) -> Outcome:
    """Run `paths` with pytest in stages; `workers` > 1 spreads the parallel stage over that many xdist workers.

    `extra` is passed to every stage's pytest. Output lines (newline kept) go to `on_output`.
    """
    lanes = _lanes(paths, cwd=cwd, python=python, wall=wall, idle=idle, env=env)
    stages: list[Stage] = []
    for name, marker, alone in _STAGES:
        if name != "parallel" and name not in lanes:
            continue
        cmd = [python, "-m", "pytest", "-p", "no:cacheprovider", "-q", "-m", marker, *extra]
        if workers > 1 and not alone:
            cmd += ["-n", str(workers)]
        result = run_process([*cmd, *paths], cwd=cwd, env=env, on_stdout=on_output, on_stderr=on_output, timeout=wall, idle=idle)
        stages.append(Stage(name, result.returncode, result.secs, result.timed_out))
        if result.timed_out and name == "parallel":
            break  # a stopped run says nothing about the stages after it
    return Outcome(tuple(stages))
