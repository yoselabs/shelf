"""git_porcelain — the pure git surface (package tests).

Exercised against REAL temp git repos (higher fidelity than mocking subprocess;
git is present in CI), plus the host-agnostic boundary invariant.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import git_porcelain as git
import pytest
from git_porcelain import GitError


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "Tester")


def test_is_repo_true_inside_repo_false_outside(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    assert git.is_repo(repo) is True
    plain = tmp_path / "plain"
    plain.mkdir()
    assert git.is_repo(plain) is False


def test_run_git_returns_stdout_and_fails_loud(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "seed.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "seed")
    branch = git.run_git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    assert branch == "main"
    with pytest.raises(GitError):
        git.run_git(repo, "not-a-real-subcommand")


def test_sync_status_clean_then_dirty(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "a.md").write_text("hi\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    st = git.sync_status(repo)
    assert st["branch"] == "main"
    assert st["clean"] is True
    assert st["changed_files"] == 0
    assert st["conflict_paused"] is False

    (repo / "a.md").write_text("changed\n", encoding="utf-8")
    st2 = git.sync_status(repo)
    assert st2["clean"] is False
    assert st2["changed_files"] == 1


def test_readiness_local_only(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    r = git.readiness(repo, check_push=False)
    assert r["is_repo"] is True
    assert r["identity"] is True  # user.email set
    assert r["remote"] is False
    assert r["push_access"] is None  # skipped


def test_dirty_rels_lists_untracked_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "sub").mkdir()
    (repo / "sub" / "new.md").write_text("x\n", encoding="utf-8")
    rels = git.dirty_rels(repo)
    assert "sub/new.md" in rels  # -uall expands the untracked dir to the file


def test_unmerged_paths_empty_when_no_conflict(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    assert git.unmerged_paths(repo) == []


def test_has_conflict_markers(tmp_path: Path) -> None:
    good = tmp_path / "good.md"
    good.write_text("clean\n", encoding="utf-8")
    assert git.has_conflict_markers(good) is False
    bad = tmp_path / "bad.md"
    bad.write_text("<<<<<<< ours\na\n=======\nb\n>>>>>>> theirs\n", encoding="utf-8")
    assert git.has_conflict_markers(bad) is True


# --- boundary invariant: git_porcelain stays host-agnostic -----------------------

_SRC = Path(__file__).resolve().parents[1] / "src" / "git_porcelain"


def test_git_porcelain_imports_no_host() -> None:
    offenders: list[str] = []
    for py in _SRC.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders += [f"{py.name}: import {a.name}" for a in node.names if a.name.split(".")[0] in {"a2kay", "a2effect", "a2kit"}]
            elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in {"a2kay", "a2effect", "a2kit"}:
                offenders.append(f"{py.name}: from {node.module}")
    assert not offenders, f"git_porcelain must stay host-agnostic; found: {offenders}"
