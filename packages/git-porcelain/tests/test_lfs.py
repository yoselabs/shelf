"""git_porcelain — git LFS: configure a repo, find the paths LFS owns, move objects before
the refs that need them.

Real temp repos and a real bare remote (git-lfs speaks to a local path remote through its
standalone transfer agent); no subprocess mocking.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import git_porcelain as git
import pytest
from git_porcelain import Identity, RemoteError

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.skipif(not git.lfs_available(), reason="git-lfs is not installed")

ROBIN = Identity("Robin Vale", "robin@example.com")
BOT = Identity("a2kay", "a2kay@example.invalid")
ATTRIBUTES = "*.png filter=lfs diff=lfs merge=lfs -text\n"
PNG = bytes(range(256)) * 40


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout


def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No global or system config: a filter can only come from the repo's own config."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / ".gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("GIT_LFS_SKIP_SMUDGE", raising=False)


def _repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / ".gitattributes").write_text(ATTRIBUTES, encoding="utf-8")
    return repo


def _commit_png(repo: Path, name: str = "scan.png", data: bytes = PNG) -> str:
    (repo / name).write_bytes(data)
    sha = git.commit_paths(repo, [".gitattributes", name], name, author=ROBIN, committer=BOT)
    assert sha is not None
    return sha


def _with_remote(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    repo = _repo(tmp_path)
    git.lfs_setup(repo)
    _commit_png(repo)
    _git(repo, "remote", "add", "origin", str(remote))
    git.lfs_push(repo, "origin", "main")
    _git(repo, "push", "-q", "-u", "origin", "main")
    return repo, remote


def _clone(tmp_path: Path, remote: Path, name: str) -> Path:
    """A clone made with LFS configured (as the server configures it on start)."""
    target = tmp_path / name
    _git(tmp_path, "clone", "-q", "--no-checkout", str(remote), str(target))
    git.lfs_setup(target)
    _git(target, "checkout", "-q", "main")
    return target


def test_lfs_available_is_true_here() -> None:
    assert git.lfs_available() is True


def test_lfs_available_is_false_without_git_lfs_on_the_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    real_git = shutil.which("git")
    assert real_git is not None
    (bin_dir / "git").symlink_to(real_git)
    monkeypatch.setenv("PATH", str(bin_dir))

    assert git.lfs_available() is False
    assert git.lfs_setup(tmp_path) is False


def test_setup_makes_a_commit_store_a_pointer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate(tmp_path, monkeypatch)
    repo = _repo(tmp_path)

    assert git.lfs_setup(repo) is True
    _commit_png(repo)

    committed = _git(repo, "show", "HEAD:scan.png")
    assert committed.startswith("version https://git-lfs.github.com/spec/v1")
    assert (repo / "scan.png").read_bytes() == PNG


def test_setup_marks_the_filter_required_and_installs_no_hooks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate(tmp_path, monkeypatch)
    repo = _repo(tmp_path)

    git.lfs_setup(repo)

    assert _git(repo, "config", "--local", "filter.lfs.required").strip() == "true"
    hooks = repo / ".git" / "hooks"
    assert not [p for p in hooks.iterdir() if not p.name.endswith(".sample")]


def test_setup_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate(tmp_path, monkeypatch)
    repo = _repo(tmp_path)

    git.lfs_setup(repo)
    config = (repo / ".git" / "config").read_text(encoding="utf-8")
    git.lfs_setup(repo)

    assert (repo / ".git" / "config").read_text(encoding="utf-8") == config


def test_checkout_after_fetch_replaces_pointer_files_with_their_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate(tmp_path, monkeypatch)
    _, remote = _with_remote(tmp_path)
    plain = tmp_path / "plain"
    _git(tmp_path, "clone", "-q", str(remote), str(plain))  # no filter: pointers on disk
    assert (plain / "scan.png").read_bytes().startswith(b"version https://git-lfs")

    git.lfs_setup(plain)  # touches no working-tree file
    assert (plain / "scan.png").read_bytes().startswith(b"version https://git-lfs")
    git.lfs_fetch(plain, "origin", "main")
    git.lfs_checkout(plain)

    assert (plain / "scan.png").read_bytes() == PNG
    assert _git(plain, "status", "--porcelain") == ""


def test_lfs_paths_names_the_paths_the_filter_owns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate(tmp_path, monkeypatch)
    repo = _repo(tmp_path)

    owned = git.lfs_paths(repo, ["a/scan.png", "notes.md", "dir with space/b.png"])

    assert owned == {"a/scan.png", "dir with space/b.png"}
    assert git.lfs_paths(repo, []) == set()


def test_push_after_lfs_push_gives_a_clone_the_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate(tmp_path, monkeypatch)
    _, remote = _with_remote(tmp_path)

    clone = _clone(tmp_path, remote, "clone")

    assert (clone / "scan.png").read_bytes() == PNG


def test_lfs_fetch_before_merge_brings_bytes_not_pointers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate(tmp_path, monkeypatch)
    repo, remote = _with_remote(tmp_path)
    other = _clone(tmp_path, remote, "other")
    deck = bytes(reversed(PNG))
    _commit_png(other, "deck.png", deck)
    git.lfs_push(other, "origin", "main")
    _git(other, "push", "-q", "origin", "main")

    git.fetch(repo, "origin")
    git.lfs_fetch(repo, "origin", "origin/main")
    result = git.merge(repo, "origin/main", author=BOT, committer=BOT, message="sync")

    assert result.state == "fast_forward"
    assert (repo / "deck.png").read_bytes() == deck


def test_lfs_fetch_of_a_missing_object_raises_remote_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate(tmp_path, monkeypatch)
    repo, remote = _with_remote(tmp_path)
    other = _clone(tmp_path, remote, "other")
    _commit_png(other, "deck.png", bytes(reversed(PNG)))
    git.lfs_push(other, "origin", "main")
    _git(other, "push", "-q", "origin", "main")
    shutil.rmtree(remote / "lfs" / "objects")

    git.fetch(repo, "origin")
    with pytest.raises(RemoteError):
        git.lfs_fetch(repo, "origin", "origin/main")

    assert not (repo / "deck.png").exists()
