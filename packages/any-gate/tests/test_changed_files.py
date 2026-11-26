"""any_gate.changed: a per-file linter sees the files changed against the base, or everything when it cannot tell."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
from any_gate import changed

if TYPE_CHECKING:
    from pathlib import Path


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _write(repo: Path, name: str, text: str = "x\n") -> None:
    (repo / name).parent.mkdir(parents=True, exist_ok=True)
    (repo / name).write_text(text)


@pytest.fixture
def clone(tmp_path: Path) -> Path:
    """A clone whose branch tracks origin/main, with three committed files and an ignore rule."""
    origin, work = tmp_path / "origin.git", tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    for name in ("a.py", "b.py", "keep.sh", "pyproject.toml"):
        _write(work, name)
    _write(work, ".gitignore", "ignored.py\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "base")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-q", "-u", "origin", "main")
    return work


def test_nothing_changed_selects_nothing(clone: Path) -> None:
    assert changed.select(clone, ["*.py"]) == []


def test_committed_staged_unstaged_and_untracked_files_are_selected_and_ignored_ones_are_not(clone: Path) -> None:
    _write(clone, "committed.py")
    _git(clone, "add", "committed.py")
    _git(clone, "commit", "-q", "-m", "c")
    _write(clone, "staged.py")
    _git(clone, "add", "staged.py")
    _write(clone, "a.py", "changed\n")
    _write(clone, "sub/untracked.py")
    _write(clone, "ignored.py")
    _write(clone, "other.txt")
    assert changed.select(clone, ["*.py"]) == ["a.py", "committed.py", "staged.py", "sub/untracked.py"]


def test_a_deleted_file_is_not_selected(clone: Path) -> None:
    (clone / "a.py").unlink()
    _git(clone, "rm", "-q", "b.py")
    assert changed.select(clone, ["*.py"]) == []


def test_a_renamed_file_is_selected_by_its_new_path(clone: Path) -> None:
    _git(clone, "mv", "a.py", "moved.py")
    assert changed.select(clone, ["*.py"]) == ["moved.py"]


def test_a_move_changes_both_its_old_and_its_new_path(clone: Path) -> None:
    _git(clone, "mv", "a.py", "moved.py")
    assert changed.changed(clone) == ["a.py", "moved.py"]


def test_a_changed_config_file_selects_every_matching_file(clone: Path) -> None:
    _write(clone, "pyproject.toml", "[tool.ruff]\n")
    assert changed.select(clone, ["*.py"], ["pyproject.toml"]) == ["a.py", "b.py"]
    assert changed.select(clone, ["*.py"]) == []


def test_scope_all_selects_every_matching_file_even_ignoring_nothing_changed(clone: Path) -> None:
    _write(clone, "ignored.py")
    assert changed.select(clone, ["*.py"], scope="all") == ["a.py", "b.py"]


def test_no_upstream_selects_everything(clone: Path) -> None:
    _git(clone, "checkout", "-q", "-b", "loose")
    assert changed.select(clone, ["*.py"]) == ["a.py", "b.py"]


def test_outside_a_git_repo_selects_everything(tmp_path: Path) -> None:
    _write(tmp_path, "a.py")
    _write(tmp_path, "node_modules/x.py")
    _write(tmp_path, "d/b.sh")
    assert changed.select(tmp_path, ["*.py"]) == ["a.py"]


def test_the_command_prints_nul_separated_paths(clone: Path) -> None:
    _write(clone, "a.py", "changed\n")
    _write(clone, "dir/c.py")
    done = subprocess.run([sys.executable, "-m", "any_gate", "changed", "--repo", str(clone), "*.py"], capture_output=True, check=True)
    assert done.stdout == b"a.py\0dir/c.py\0"


def test_a_skip_glob_drops_a_match(clone: Path) -> None:
    _write(clone, "Dockerfile")
    _write(clone, "Dockerfile.dockerignore")
    assert changed.select(clone, ["*Dockerfile", "*Dockerfile.*"], skip=["*.dockerignore"]) == ["Dockerfile"]


def test_a_deleted_config_file_selects_everything(clone: Path) -> None:
    (clone / "pyproject.toml").unlink()
    assert changed.select(clone, ["*.py"], ["pyproject.toml"]) == ["a.py", "b.py"]
