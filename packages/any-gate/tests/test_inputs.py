"""any_gate.inputs: a step that declares its input files and whose inputs did not change is not started (no process, no file read)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from any_gate import inputs

REPO_INPUTS = Path(__file__).resolve().parents[3] / inputs.FILE
# A stand-in for `just`: records each step it is asked to run, one line per process, in $RUNS.
FAKE = '#!/bin/sh\necho "$1" >> "$RUNS"\n'
# A stand-in for `git` ahead of the real one on PATH: records each process, then runs the real git.
GIT = '#!/bin/sh\necho "$*" >> "$GITS"\nexec "$REAL_GIT" "$@"\n'


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def clone(tmp_path: Path) -> Path:
    """A clone tracking origin/main, with the gate's own gate-inputs.toml committed."""
    origin, work = tmp_path / "origin.git", tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    shutil.copy(REPO_INPUTS, work / inputs.FILE)
    (work / "a.py").write_text("x\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "base")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-q", "-u", "origin", "main")
    return work


def _steps(clone: Path, tmp_path: Path, *names: str, flags: tuple[str, ...] = ()) -> tuple[list[str], list[str]]:
    """Run `any_gate steps`; return the steps the runner was started for and the git commands it spawned."""
    fake, shim = tmp_path / "fake-just", tmp_path / "bin" / "git"
    shim.parent.mkdir(exist_ok=True)
    fake.write_text(FAKE)
    shim.write_text(GIT)
    for path in (fake, shim):
        path.chmod(0o755)
    runs, gits = tmp_path / "runs", tmp_path / "gits"
    env = {
        **os.environ,
        "RUNS": str(runs),
        "GITS": str(gits),
        "REAL_GIT": shutil.which("git") or "git",
        "PATH": f"{shim.parent}{os.pathsep}{os.environ['PATH']}",
    }
    cmd = [sys.executable, "-m", "any_gate", "steps", "--runner", str(fake), "--repo", str(clone), *flags, *names]
    subprocess.run(cmd, cwd=clone, env=env, capture_output=True, text=True, check=False)
    read = lambda p: p.read_text().split() if p.is_file() else []  # noqa: E731
    return read(runs), (gits.read_text().splitlines() if gits.is_file() else [])


STEPS = sorted(name for name, value in tomllib.loads(REPO_INPUTS.read_text()).items() if isinstance(value, list))  # [wide] is a table


def test_the_gates_own_steps_are_all_declared() -> None:
    assert {"lint-changed", "typecheck", "test", "blueprint"} <= set(STEPS)


@pytest.mark.parametrize("step", STEPS)
def test_golden_an_unchanged_tree_starts_no_process_for_a_step_and_asks_git_at_most_three_times(
    step: str, clone: Path, tmp_path: Path
) -> None:
    runs, gits = _steps(clone, tmp_path, step)
    assert runs == []
    assert len(gits) <= 3


def test_a_step_with_a_matching_changed_file_runs_and_one_without_is_skipped(clone: Path, tmp_path: Path) -> None:
    (clone / "b.py").write_text("y\n")
    runs, _ = _steps(clone, tmp_path, "typecheck", "guard")
    assert runs == ["typecheck"]  # guard reads only pyproject.toml files


def test_a_step_with_no_declaration_always_runs(clone: Path, tmp_path: Path) -> None:
    runs, _ = _steps(clone, tmp_path, "unlisted", "typecheck")
    assert runs == ["unlisted"]


def test_a_changed_declaration_file_runs_every_step(clone: Path, tmp_path: Path) -> None:
    (clone / inputs.FILE).write_text((clone / inputs.FILE).read_text() + "\n# edited\n")
    runs, _ = _steps(clone, tmp_path, "guard", "typecheck")
    assert sorted(runs) == ["guard", "typecheck"]


def test_all_runs_every_step_whatever_changed(clone: Path, tmp_path: Path) -> None:
    runs, gits = _steps(clone, tmp_path, "guard", "typecheck", flags=("--all",))
    assert sorted(runs) == ["guard", "typecheck"]
    assert gits == []


def test_no_base_runs_every_step(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    shutil.copy(REPO_INPUTS, work / inputs.FILE)
    runs, _ = _steps(work, tmp_path, "guard")
    assert runs == ["guard"]


def test_a_skipped_step_is_reported_as_a_skipped_line(clone: Path, tmp_path: Path) -> None:
    fake = tmp_path / "fake-just"
    fake.write_text(FAKE)
    fake.chmod(0o755)
    done = subprocess.run(
        [sys.executable, "-m", "any_gate", "steps", "--runner", str(fake), "--repo", str(clone), "guard"],
        cwd=clone,
        env={**os.environ, "RUNS": str(tmp_path / "r")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0
    assert "skipped guard: none of its declared inputs changed" in done.stderr


def test_moving_a_file_out_of_a_steps_folder_still_starts_that_step(clone: Path) -> None:
    (clone / inputs.FILE).write_text('ui = ["ui/*"]\n')
    (clone / "ui").mkdir()
    (clone / "ui" / "x.ts").write_text("x\n")
    _git(clone, "add", "-A")
    _git(clone, "commit", "-q", "-m", "ui")
    _git(clone, "push", "-q")
    assert "ui" in inputs.unaffected(clone, ["ui"])  # pushed: nothing changed since the base, the step is skipped
    _git(clone, "mv", "ui/x.ts", "docs_x.ts")
    assert inputs.unaffected(clone, ["ui"]) == {}  # the old path is a changed input of `ui`
