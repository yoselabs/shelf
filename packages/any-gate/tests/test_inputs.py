"""any_gate.inputs: a step that declares its input files and whose inputs did not change is not started (no process, no file read)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from any_gate import inputs

ROOT = Path(__file__).resolve().parents[3]
REPO_INPUTS = ROOT / inputs.FILE
DEFAULTS = ROOT / inputs.DEFAULTS
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
def fresh(tmp_path: Path) -> Path:
    """A clone tracking origin/main, with the gate's own gate-inputs.toml committed; no gate has passed it."""
    origin, work = tmp_path / "origin.git", tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    shutil.copy(REPO_INPUTS, work / inputs.FILE)
    (work / ".blueprint").mkdir()
    shutil.copy(DEFAULTS, work / inputs.DEFAULTS)
    (work / "a.py").write_text("x\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "base")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-q", "-u", "origin", "main")
    return work


@pytest.fixture
def clone(fresh: Path) -> Path:
    """The same clone after a gate passed it: its empty change set means "nothing to judge"."""
    _green(fresh)
    return fresh


def _green(clone: Path) -> None:
    """Record HEAD's tree as passed by `check`, the way a finished gate does."""
    for verb in ("start", "passed"):
        subprocess.run([sys.executable, "-m", "any_gate", verb, "--repo", str(clone)], check=True, capture_output=True)


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


STEPS = sorted(inputs.declared(ROOT))  # the defaults plus the repo's exceptions


def test_the_gates_own_steps_are_all_declared() -> None:
    assert {"lint-changed", "typecheck", "test", "blueprint"} <= set(STEPS)


@pytest.mark.parametrize("step", STEPS)
def test_golden_an_unchanged_tree_starts_no_process_for_a_step_and_asks_git_at_most_three_times(
    step: str, clone: Path, tmp_path: Path
) -> None:
    runs, gits = _steps(clone, tmp_path, step)
    assert runs == []
    assert len(gits) <= 7  # the change set (3), the git dir, and the green tree record (status, tree key)


def test_an_empty_change_set_no_gate_passed_runs_every_declared_step(fresh: Path, tmp_path: Path) -> None:
    runs, _ = _steps(fresh, tmp_path, "typecheck", "guard")
    assert sorted(runs) == ["guard", "typecheck"]  # a fresh clone, a merge or a reset: nothing "changed", so nothing was judged


def test_a_step_with_a_matching_changed_file_runs_and_one_without_is_skipped(clone: Path, tmp_path: Path) -> None:
    (clone / "b.py").write_text("y\n")
    runs, _ = _steps(clone, tmp_path, "typecheck", "scripts")
    assert runs == ["typecheck"]  # scripts reads only shell files


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
        [sys.executable, "-m", "any_gate", "steps", "--runner", str(fake), "--repo", str(clone), "scripts"],
        cwd=clone,
        env={**os.environ, "RUNS": str(tmp_path / "r")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0
    assert re.search(r"skipped scripts: none of .+ changed", done.stderr)


def test_moving_a_file_out_of_a_steps_folder_still_starts_that_step(clone: Path) -> None:
    (clone / inputs.FILE).write_text('ui = ["ui/*"]\n')
    (clone / "ui").mkdir()
    (clone / "ui" / "x.ts").write_text("x\n")
    _git(clone, "add", "-A")
    _git(clone, "commit", "-q", "-m", "ui")
    _git(clone, "push", "-q")
    assert "ui" in inputs.unaffected(clone, ["ui"], lambda: True)  # pushed: nothing changed since the base, the step is skipped
    _git(clone, "mv", "ui/x.ts", "docs_x.ts")
    assert inputs.unaffected(clone, ["ui"]) == {}  # the old path is a changed input of `ui`


def _repo_with(tmp_path: Path, defaults: str | None, repo_file: str | None) -> Path:
    """A clone with the given default and repo declaration files committed; one gate has passed it."""
    origin, work = tmp_path / "o.git", tmp_path / "w"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    if defaults is not None:
        (work / ".blueprint").mkdir()
        (work / inputs.DEFAULTS).write_text(defaults)
    if repo_file is not None:
        (work / inputs.FILE).write_text(repo_file)
    (work / "a.py").write_text("x\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "base")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-q", "-u", "origin", "main")
    _green(work)
    return work


def test_a_repo_with_no_declaration_file_skips_on_the_rendered_defaults(tmp_path: Path) -> None:
    work = _repo_with(tmp_path, 'typecheck = ["*.py"]\nscripts = ["*.sh"]\n', None)
    (work / "b.py").write_text("y\n")
    runs, _ = _steps(work, tmp_path, "typecheck", "scripts")
    assert runs == ["typecheck"]


def test_a_repo_list_widens_the_default_and_never_narrows_it(tmp_path: Path) -> None:
    work = _repo_with(tmp_path, 'typecheck = ["*.py"]\n', 'typecheck = ["*.cfg"]\n')
    assert inputs.declared(work)["typecheck"] == ["*.py", "*.cfg"]
    (work / "x.cfg").write_text("c\n")
    assert _steps(work, tmp_path, "typecheck")[0] == ["typecheck"]
    (work / "x.cfg").unlink()
    (work / "b.py").write_text("y\n")
    again = tmp_path / "again"
    again.mkdir()
    assert _steps(work, again, "typecheck")[0] == ["typecheck"]  # the default still applies


def test_a_narrowed_step_uses_only_the_repo_list(tmp_path: Path) -> None:
    repo_file = 'typecheck = ["src/*.py"]\n[narrow]\ntypecheck = "only src is typed"\n'
    work = _repo_with(tmp_path, 'typecheck = ["*.py"]\n', repo_file)
    assert inputs.declared(work)["typecheck"] == ["src/*.py"]


def test_a_step_with_neither_default_nor_declaration_always_runs(tmp_path: Path) -> None:
    work = _repo_with(tmp_path, 'typecheck = ["*.py"]\n', None)
    assert _steps(work, tmp_path, "custom")[0] == ["custom"]


def test_a_changed_defaults_file_runs_every_step(tmp_path: Path) -> None:
    work = _repo_with(tmp_path, 'typecheck = ["*.py"]\nscripts = ["*.sh"]\n', None)
    (work / inputs.DEFAULTS).write_text('typecheck = ["*.py"]\nscripts = ["*.sh"]\n# edited\n')
    assert sorted(_steps(work, tmp_path, "typecheck", "scripts")[0]) == ["scripts", "typecheck"]


def test_a_step_says_in_one_line_why_it_runs_and_a_skipped_one_why_not(clone: Path) -> None:
    (clone / "b.py").write_text("y\n")
    (clone / "c.py").write_text("z\n")
    skips, runs = inputs.explain(clone, ["typecheck", "scripts"])
    assert re.fullmatch(r"run typecheck: 2 changed \(.*\.py.*\)", runs["typecheck"])
    assert skips["scripts"].startswith("skipped scripts: none of ")
    assert "scripts" not in runs


def test_a_step_with_no_declaration_says_so(clone: Path) -> None:
    assert inputs.explain(clone, ["unlisted"])[1] == {"unlisted": "run unlisted: declares no inputs"}


def test_a_fresh_tree_says_no_gate_passed_it(fresh: Path) -> None:
    assert inputs.explain(fresh, ["typecheck"])[1] == {"typecheck": "run typecheck: no gate passed this tree"}


def test_a_changed_gate_definition_says_so(clone: Path) -> None:
    (clone / inputs.FILE).write_text((clone / inputs.FILE).read_text() + "\n# edited\n")
    assert inputs.explain(clone, ["typecheck"])[1] == {"typecheck": "run typecheck: gate definition changed"}


def test_all_says_every_step_runs_because_of_it(clone: Path, tmp_path: Path) -> None:
    done = subprocess.run(
        [sys.executable, "-m", "any_gate", "steps", "--all", "--runner", "true", "--repo", str(clone), "typecheck"],
        cwd=clone,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "run typecheck: --all" in done.stderr
