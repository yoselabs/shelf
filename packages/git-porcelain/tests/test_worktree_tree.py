"""A folder on disk reads as a Tree of the same shape as a commit's: same listing, same ids, same bytes."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from git_porcelain import RealRepo, blob_sha, worktree_tree
from git_porcelain.testing import apply_hermetic_env, git

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch: pytest.MonkeyPatch) -> None:
    apply_hermetic_env(monkeypatch)


def _committed(root: Path, files: dict[str, bytes]) -> RealRepo:
    git(root, "init", "-q", "-b", "main")
    for rel, data in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    git(root, "add", "-A")
    git(root, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "root")
    return RealRepo(root, ambient=dict(os.environ))


def test_blob_sha_is_the_id_git_gives_a_file(tmp_path: Path) -> None:
    repo = _committed(tmp_path, {"a.md": b"one\r\n\xff"})
    tree = repo.tree("HEAD")
    assert tree is not None
    assert tree.files["a.md"][1] == blob_sha(b"one\r\n\xff")


def test_a_worktree_equals_the_commit_it_was_committed_as(tmp_path: Path) -> None:
    repo = _committed(tmp_path, {"kb/a.md": b"one", "kb/sub/b.md": b"two", "kb/run.sh": b"#!/bin/sh\n", "top": b"x"})
    (tmp_path / "kb/run.sh").chmod(0o755)
    git(tmp_path, "add", "-A")
    git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "exec")
    committed = repo.tree("HEAD:kb")
    on_disk = worktree_tree(tmp_path, "kb")
    assert committed is not None
    assert on_disk is not None
    assert dict(on_disk.files) == dict(committed.files)
    assert on_disk.sha == committed.sha
    assert on_disk.read_many(["a.md", "sub/b.md", "gone"]) == committed.read_many(["a.md", "sub/b.md", "gone"])


def test_edits_show_and_the_ids_move(tmp_path: Path) -> None:
    repo = _committed(tmp_path, {"kb/a.md": b"one"})
    (tmp_path / "kb/a.md").write_bytes(b"edited")
    (tmp_path / "kb/new.md").write_bytes(b"new")
    committed, on_disk = repo.tree("HEAD:kb"), worktree_tree(tmp_path, "kb")
    assert committed is not None
    assert on_disk is not None
    assert sorted(on_disk.files) == ["a.md", "new.md"]
    assert on_disk.sha != committed.sha
    assert on_disk.read("a.md") == b"edited"


def test_the_whole_root_skips_dot_git_and_the_missing_is_none(tmp_path: Path) -> None:
    _committed(tmp_path, {"a": b"1"})
    whole = worktree_tree(tmp_path)
    assert whole is not None
    assert sorted(whole.files) == ["a"]
    assert whole.read(".git/HEAD") is None
    assert worktree_tree(tmp_path, "gone") is None
    assert worktree_tree(tmp_path, "a") is None


def test_read_stays_inside_the_folder_and_to_regular_files(tmp_path: Path) -> None:
    (tmp_path / "kb").mkdir()
    (tmp_path / "kb/a.md").write_bytes(b"one")
    (tmp_path / "secret").write_bytes(b"s")
    (tmp_path / "kb/link").symlink_to(tmp_path / "secret")
    tree = worktree_tree(tmp_path, "kb")
    assert tree is not None
    assert list(tree.files) == ["a.md"]
    assert tree.read("../secret") is None
    assert tree.read("link") is None
    assert tree.read("/etc/passwd") is None
    assert tree.read("sub") is None
