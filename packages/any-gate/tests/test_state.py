"""Gate state: the tree a gate passed is remembered, so a push does not run the gate again on exactly that content.

A tree is the content `git add -A` would commit (tracked and untracked files, ignored ones left out). The record is a receipt named for the
gate, keyed by the tree and the upstream merge-base; any doubt runs the gate.
"""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING, Protocol

import pytest
from any_gate import GateState, Receipts

if TYPE_CHECKING:
    from pathlib import Path


class Git(Protocol):
    """The throwaway repo `conftest.py` makes."""

    root: Path
    env: dict[str, str]

    def git(self, *args: str) -> str: ...

    def write(self, rel: str, text: str) -> None: ...

    def commit(self, message: str = "c") -> None: ...


@pytest.fixture
def state(repo: Git, tmp_path: Path) -> GateState:
    return GateState(repo.root, Receipts(tmp_path / "receipts.json"))


def _green(state: GateState, *, edit: tuple[Git, str] | None = None, gate: str = "check") -> None:
    state.start()
    if edit:
        edit[0].write(edit[1], "edited during the run\n")
    state.passed(gate)


def test_a_clean_tree_that_passed_the_gate_may_skip_it(state: GateState) -> None:
    _green(state)
    assert state.green("check")


def test_a_tree_checked_dirty_then_committed_whole_is_the_tree_that_passed(repo: Git, state: GateState) -> None:
    repo.write("app.py", "x = 2\n")
    repo.write("new.py", "y = 1\n")
    _green(state)
    repo.commit()
    assert state.green("check")


def test_nothing_is_skipped_before_a_gate_passed(state: GateState) -> None:
    assert not state.green("check")


def test_a_gate_that_never_reached_passed_records_nothing(state: GateState) -> None:
    state.start()  # a failed step stops the gate before `passed`
    assert not state.green("check")


def test_a_tree_edited_during_the_run_records_nothing(repo: Git, state: GateState) -> None:
    _green(state, edit=(repo, "app.py"))
    repo.commit()  # the edited content is what is pushed, and no gate saw it whole
    assert not state.green("check")


def test_a_dirty_working_tree_is_never_skipped(repo: Git, state: GateState) -> None:
    _green(state)
    repo.write("scratch.py", "z = 1\n")
    assert not state.green("check")


def test_another_commit_runs_the_gate_again(repo: Git, state: GateState) -> None:
    _green(state)
    repo.write("app.py", "x = 3\n")
    repo.commit()
    assert not state.green("check")


def test_a_pass_of_another_gate_does_not_count(state: GateState) -> None:
    _green(state, gate="check-all")
    assert not state.green("check")


def test_a_worktree_shares_the_record_of_its_checkout(repo: Git, tmp_path: Path) -> None:
    receipts = Receipts(tmp_path / "shared.json")
    _green(GateState(repo.root, receipts))
    other = tmp_path / "second"
    repo.git("worktree", "add", "-q", "-b", "other", str(other))
    assert GateState(other, receipts).green("check")  # the same tree, a different checkout


def test_outside_a_git_repo_nothing_is_recorded_and_nothing_is_skipped(tmp_path: Path) -> None:
    state = GateState(tmp_path, Receipts(tmp_path / "r.json"))
    state.start()
    assert not state.passed("check")
    assert not state.green("check")


def _push(repo: Git, receipts: Path, **env: str) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", "any_gate", "pre-push", "--repo", str(repo.root), "--receipts", str(receipts), "--gate", "check"]
    cmd += ["--", "sh", "-c", "echo gate ran; exit 9"]
    return subprocess.run(cmd, cwd=repo.root, env={**repo.env, **env}, capture_output=True, text=True, check=False)


def _record(repo: Git, receipts: Path) -> None:
    for verb in (["start"], ["passed", "--gate", "check"]):
        cmd = [sys.executable, "-m", "any_gate", verb[0], "--repo", str(repo.root), "--receipts", str(receipts), *verb[1:]]
        subprocess.run(cmd, cwd=repo.root, env=repo.env, check=True, capture_output=True)


def test_the_push_hook_skips_the_gate_on_a_tree_that_passed_it(repo: Git, tmp_path: Path) -> None:
    receipts = tmp_path / "r.json"
    _record(repo, receipts)
    pushed = _push(repo, receipts, PRE_COMMIT_TO_REF=repo.git("rev-parse", "HEAD"))
    assert (pushed.returncode, pushed.stdout) == (0, "")
    assert "passed `check`" in pushed.stderr


def test_the_push_hook_runs_the_gate_and_returns_its_exit_code_on_any_doubt(repo: Git, tmp_path: Path) -> None:
    pushed = _push(repo, tmp_path / "r.json")
    assert (pushed.returncode, pushed.stdout) == (9, "gate ran\n")


def test_the_push_hook_runs_the_gate_when_pushing_a_commit_that_is_not_head(repo: Git, tmp_path: Path) -> None:
    receipts = tmp_path / "r.json"
    _record(repo, receipts)
    pushed = _push(repo, receipts, PRE_COMMIT_TO_REF="0" * 40)
    assert (pushed.returncode, pushed.stdout) == (9, "gate ran\n")
