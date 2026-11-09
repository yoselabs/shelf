"""Command-boundary guarantees for worktree reads and removal diagnostics."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from git_porcelain import GitUnavailable, Identity, IndexLocked, NotARepo, RealRepo, WorktreeRemoveRefused
from git_porcelain.real_done import Done
from git_porcelain.testing import apply_hermetic_env, git

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


@pytest.mark.parametrize("intro", ["introductory diagnostic", "error: introductory diagnostic"])
def test_remove_refusal_keeps_the_first_diagnostic_and_final_hint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, intro: str) -> None:
    repo = RealRepo(tmp_path)
    reason = "fatal: " + "long path " * 100 + "contains modified or untracked files"
    calls: list[tuple[str, ...]] = []

    def run(cwd: Path, *args: str, check: bool = True) -> Done:
        calls.append(args)
        return Done(128, b"", f"{intro}\n{reason}\n\n")

    monkeypatch.setattr(repo, "run", run)
    with pytest.raises(WorktreeRemoveRefused) as caught:
        repo.drop_worktree(tmp_path / "w", missing_ok=False)
    expected = intro if intro.startswith("error:") else reason
    assert caught.value.reason == expected
    message = f"git worktree remove exited 128: {expected}"
    assert str(caught.value) == message + (f" | {reason}" if expected != reason else "")
    assert calls == [("worktree", "remove", str(tmp_path / "w"))]


def test_locked_worktree_removal_keeps_fatal_reason_and_hint(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "commit", "--allow-empty", "-qm", "seed")
    repo = RealRepo(tmp_path)
    path = tmp_path / "locked"
    repo.add_worktree(path, "HEAD")
    git(tmp_path, "worktree", "lock", "--reason", "contract lock", str(path))

    with pytest.raises(WorktreeRemoveRefused) as caught:
        repo.drop_worktree(path, missing_ok=False)

    assert caught.value.reason == "fatal: cannot remove a locked working tree, lock reason: contract lock"
    assert str(caught.value).startswith(f"git worktree remove exited 128: {caught.value.reason}")
    assert " | use 'remove -f -f' to override or unlock first" in str(caught.value)


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


@pytest.mark.parametrize("common_symlink", [False, True])
def test_identity_is_canonical_across_linked_and_symlinked_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, common_symlink: bool
) -> None:
    """shelf-7qsd: all paths into one local repository name the same canonical common directory."""
    apply_hermetic_env(monkeypatch, identity=Identity("Test", "test@example.invalid"), home=tmp_path / "home")
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "-q", "-b", "main")
    git(main, "commit", "--allow-empty", "-qm", "seed")
    common = main / ".git"
    if common_symlink:
        common = tmp_path / "metadata"
        (main / ".git").rename(common)
        (main / ".git").symlink_to(common, target_is_directory=True)
    linked = tmp_path / "linked"
    git(main, "worktree", "add", "--detach", str(linked), "HEAD")
    alias = tmp_path / "alias"
    alias.symlink_to(main, target_is_directory=True)
    identities = [RealRepo(path, memoize=False).identity() for path in (main, linked, alias)]
    assert all(value.common_dir == common.resolve() for value in identities)
    assert len({value.key for value in identities}) == 1
    assert all(value.origin_url is None for value in identities)
