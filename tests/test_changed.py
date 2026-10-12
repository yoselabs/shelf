"""tools/changed.py: a per-file linter sees the files changed against the base, or everything when it cannot tell."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import changed


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
def repo(tmp_path: Path) -> Path:
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


def test_nothing_changed_selects_nothing(repo: Path) -> None:
    assert changed.select(repo, ["*.py"]) == []


def test_committed_staged_unstaged_and_untracked_files_are_selected_and_ignored_ones_are_not(repo: Path) -> None:
    _write(repo, "committed.py")
    _git(repo, "add", "committed.py")
    _git(repo, "commit", "-q", "-m", "c")
    _write(repo, "staged.py")
    _git(repo, "add", "staged.py")
    _write(repo, "a.py", "changed\n")
    _write(repo, "sub/untracked.py")
    _write(repo, "ignored.py")
    _write(repo, "other.txt")
    assert changed.select(repo, ["*.py"]) == ["a.py", "committed.py", "staged.py", "sub/untracked.py"]


def test_a_deleted_file_is_not_selected(repo: Path) -> None:
    (repo / "a.py").unlink()
    _git(repo, "rm", "-q", "b.py")
    assert changed.select(repo, ["*.py"]) == []


def test_a_renamed_file_is_selected_by_its_new_path(repo: Path) -> None:
    _git(repo, "mv", "a.py", "moved.py")
    assert changed.select(repo, ["*.py"]) == ["moved.py"]


def test_a_changed_config_file_selects_every_matching_file(repo: Path) -> None:
    _write(repo, "pyproject.toml", "[tool.ruff]\n")
    assert changed.select(repo, ["*.py"], ["pyproject.toml"]) == ["a.py", "b.py"]
    assert changed.select(repo, ["*.py"]) == []


def test_scope_all_selects_every_matching_file_even_ignoring_nothing_changed(repo: Path) -> None:
    _write(repo, "ignored.py")
    assert changed.select(repo, ["*.py"], scope="all") == ["a.py", "b.py"]


def test_no_upstream_selects_everything(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "loose")
    assert changed.select(repo, ["*.py"]) == ["a.py", "b.py"]


def test_outside_a_git_repo_selects_everything(tmp_path: Path) -> None:
    _write(tmp_path, "a.py")
    _write(tmp_path, "node_modules/x.py")
    _write(tmp_path, "d/b.sh")
    assert changed.select(tmp_path, ["*.py"]) == ["a.py"]


def test_the_command_prints_nul_separated_paths(repo: Path) -> None:
    _write(repo, "a.py", "changed\n")
    _write(repo, "dir/c.py")
    done = subprocess.run([sys.executable, str(Path(changed.__file__)), "--repo", str(repo), "*.py"], capture_output=True, check=True)
    assert done.stdout == b"a.py\0dir/c.py\0"


def test_a_skip_glob_drops_a_match(repo: Path) -> None:
    _write(repo, "Dockerfile")
    _write(repo, "Dockerfile.dockerignore")
    assert changed.select(repo, ["*Dockerfile", "*Dockerfile.*"], skip=["*.dockerignore"]) == ["Dockerfile"]


def test_a_deleted_config_file_selects_everything(repo: Path) -> None:
    (repo / "pyproject.toml").unlink()
    assert changed.select(repo, ["*.py"], ["pyproject.toml"]) == ["a.py", "b.py"]
