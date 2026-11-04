"""Command-boundary guarantees for worktree reads and removal diagnostics."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from git_porcelain import GitUnavailable, IndexLocked, NotARepo, RealRepo, WorktreeRemoveRefused
from git_porcelain.real_done import Done

if TYPE_CHECKING:
    from pathlib import Path


def test_worktree_state_preserves_bytes_and_asks_each_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = RealRepo(tmp_path)
    raw = b"# branch.oid (initial)\0# branch.head main\0? name\xff\n\0"
    calls: list[tuple[str, ...]] = []

    def run(cwd: Path, *args: str, check: bool = True) -> Done:
        assert cwd == tmp_path
        assert not check
        calls.append(args)
        return Done(0, raw, "")

    monkeypatch.setattr(repo, "run", run)
    assert repo.worktree_state(tmp_path) == raw
    assert repo.worktree_state(tmp_path) == raw
    expected = ("--no-optional-locks", "status", "--porcelain=v2", "--branch", "-z", "--untracked-files=all")
    assert calls == [expected, expected]


@pytest.mark.parametrize(
    ("stderr", "error"),
    [
        ("fatal: not a git repository (or any of the parent directories): .git", None),
        ("fatal: this operation must be run in a work tree", None),
        ("fatal: bad object HEAD", GitUnavailable),
        ("fatal: cannot read index.lock", IndexLocked),
    ],
)
def test_worktree_state_distinguishes_absence_from_read_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stderr: str, error: type[GitUnavailable] | None
) -> None:
    repo = RealRepo(tmp_path)

    def run(cwd: Path, *args: str, check: bool = True) -> Done:
        return Done(128, b"", stderr)

    monkeypatch.setattr(repo, "run", run)
    if error is None:
        assert repo.worktree_state(tmp_path) is None
    else:
        with pytest.raises(error):
            repo.worktree_state(tmp_path)


def test_remove_refusal_keeps_the_complete_final_stderr_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = RealRepo(tmp_path)
    reason = "fatal: " + "long path " * 100 + "contains modified or untracked files"
    calls: list[tuple[str, ...]] = []

    def run(cwd: Path, *args: str, check: bool = True) -> Done:
        calls.append(args)
        return Done(128, b"", f"error: introductory diagnostic\n{reason}\n\n")

    monkeypatch.setattr(repo, "run", run)
    with pytest.raises(WorktreeRemoveRefused) as caught:
        repo.drop_worktree(tmp_path / "w", missing_ok=False)
    assert caught.value.reason == reason
    assert calls == [("worktree", "remove", str(tmp_path / "w"))]


@pytest.mark.parametrize(
    ("stderr", "error"),
    [
        ("fatal: not a git repository (or any of the parent directories): .git", NotARepo),
        ("fatal: cannot lock ref 'HEAD'", GitUnavailable),
    ],
)
def test_remove_preserves_infrastructure_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stderr: str, error: type[GitUnavailable]
) -> None:
    repo = RealRepo(tmp_path)

    def run(cwd: Path, *args: str, check: bool = True) -> Done:
        return Done(128, b"", stderr)

    monkeypatch.setattr(repo, "run", run)
    with pytest.raises(error) as caught:
        repo.drop_worktree(tmp_path / "w", missing_ok=False)
    assert not isinstance(caught.value, WorktreeRemoveRefused)
