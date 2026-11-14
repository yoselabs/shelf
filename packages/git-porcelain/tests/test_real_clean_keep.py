"""`Worktree.clean(keep=[...], ignored=True)` against real git: the reset-path guarantee a caller relies on to keep a folder (a `.venv`)
while everything else untracked or ignored goes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from git_porcelain import Identity, RealRepo
from git_porcelain.testing import apply_hermetic_env, git

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    apply_hermetic_env(monkeypatch, identity=Identity("Test", "test@example.invalid"), home=tmp_path / "home")
    root, outside = tmp_path / "work", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / ".gitignore").write_text(".venv/\nbuild/\n*.pyc\n")
    (root / "tracked.txt").write_text("t\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "seed")
    (root / ".venv" / "lib").mkdir(parents=True)
    (root / ".venv" / "lib" / "x").write_text("env\n")
    (root / "sub" / ".venv").mkdir(parents=True)
    (root / "sub" / ".venv" / "y").write_text("nested env\n")
    (root / "build").mkdir()
    (root / "build" / "o").write_text("b\n")
    (root / "a.pyc").write_text("p\n")
    (root / "untracked.txt").write_text("u\n")
    (outside / "precious").write_text("outside\n")
    return root, outside


def test_an_anchored_keep_survives_the_ignored_clean_and_everything_else_goes(work: tuple[Path, Path]) -> None:
    root, _ = work
    RealRepo(root).worktree(root).clean(["/.venv"], ignored=True)
    left = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if ".git" not in p.relative_to(root).parts and p.is_file())
    assert left == [".gitignore", ".venv/lib/x", "tracked.txt"]  # the nested sub/.venv is not the kept one


def test_the_clean_removes_a_symlink_and_never_follows_it_out_of_the_worktree(work: tuple[Path, Path]) -> None:
    root, outside = work
    (root / "link-out").symlink_to(outside)
    (root / "build" / "link-out").symlink_to(outside)
    RealRepo(root).worktree(root).clean(["/.venv"], ignored=True)
    assert not (root / "link-out").is_symlink() and not (root / "build").exists()
    assert (outside / "precious").read_text() == "outside\n"


def test_a_kept_folder_holding_a_symlink_out_is_left_whole(work: tuple[Path, Path]) -> None:
    root, outside = work
    (root / ".venv" / "out").symlink_to(outside)
    RealRepo(root).worktree(root).clean(["/.venv"], ignored=True)
    assert (root / ".venv" / "out").is_symlink() and (outside / "precious").exists()
