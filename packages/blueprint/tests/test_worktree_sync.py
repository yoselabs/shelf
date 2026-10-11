"""agents.worktrees-in-sync: no agent worktree is more than a day out of step with main."""

from __future__ import annotations

import os
import subprocess
import time
from typing import TYPE_CHECKING

from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from pathlib import Path

    from blueprint.testing import Repo

_DAY = 86_400


def _commit(cwd: Path, name: str, age_s: int) -> None:
    stamp = f"@{int(time.time()) - age_s} +0000"
    (cwd / name).write_text(name)
    env = {**os.environ, "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}
    subprocess.run(["git", "add", name], cwd=cwd, check=True)
    subprocess.run(["git", "commit", "-qm", name], cwd=cwd, check=True, env=env)


def _verdict(repo: Repo) -> tuple[Verdict, str]:
    row = next(r for r in run(repo.root, concern="agents", audit=True, env=repo.env).rows if r.id == "agents.worktrees-in-sync")
    return row.verdict, row.evidence


def _worktree(repo: Repo, name: str) -> Path:
    path = repo.root / ".worktrees" / name
    repo.git("worktree", "add", "-q", "-b", name, str(path))
    return path


def test_fresh_worktrees_pass(repo: Repo) -> None:
    _commit(repo.root, "base", 3 * _DAY)
    tree = _worktree(repo, "fresh")
    _commit(tree, "work", 3600)
    assert _verdict(repo)[0] is Verdict.PASSING


def test_work_unmerged_for_over_a_day_fails_and_is_named(repo: Repo) -> None:
    _commit(repo.root, "base", 3 * _DAY)
    tree = _worktree(repo, "slow")
    _commit(tree, "work", 2 * _DAY)
    verdict, evidence = _verdict(repo)
    assert verdict is Verdict.FAILING
    assert "slow" in evidence


def test_a_worktree_missing_day_old_main_commits_fails(repo: Repo) -> None:
    _commit(repo.root, "base", 3 * _DAY)
    _worktree(repo, "behind")
    _commit(repo.root, "main-moved", 2 * _DAY)
    verdict, evidence = _verdict(repo)
    assert verdict is Verdict.FAILING
    assert "behind" in evidence


def test_no_worktrees_is_not_applicable(repo: Repo) -> None:
    _commit(repo.root, "base", 3 * _DAY)
    assert _verdict(repo)[0] is Verdict.NOT_APPLICABLE
