"""agents.worktrees-in-sync (this worktree) and agents.other-worktrees (the audit's list of the rest): over a day out of step with main."""

from __future__ import annotations

import os
import subprocess
import time
from typing import TYPE_CHECKING

from blueprint.model import FixedBy, Verdict
from blueprint.runner import Row, run_audit

if TYPE_CHECKING:
    from pathlib import Path

    from blueprint.testing import Repo

_DAY = 86_400


def _commit(cwd: Path, name: str, age_s: int) -> None:
    stamp = f"@{int(time.time()) - age_s} +0000"
    (cwd / name).write_text(name)
    env = {**os.environ, "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}
    subprocess.run(["git", "add", name], cwd=cwd, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", name, "--no-verify"], cwd=cwd, check=True, env=env)


def _rows(repo: Repo) -> dict[str, Row]:
    return {r.id: r for r in run_audit(repo.root, concern="agents", env=repo.env).rows}


def _verdict(repo: Repo) -> tuple[Verdict, str]:
    row = _rows(repo)["agents.other-worktrees"]
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
    row = _rows(repo)["agents.other-worktrees"]
    assert row.verdict is Verdict.FAILING
    assert "slow" in row.evidence
    assert row.fixed_by is FixedBy.OWNER
    assert "rebase" not in row.remediation.lower()


def test_a_worktree_missing_day_old_main_commits_fails(repo: Repo) -> None:
    _commit(repo.root, "base", 3 * _DAY)
    _worktree(repo, "behind")
    _commit(repo.root, "main-moved", 2 * _DAY)
    row = _rows(repo)["agents.other-worktrees"]
    assert row.verdict is Verdict.FAILING
    assert "behind" in row.evidence
    assert row.fixed_by is FixedBy.OWNER
    assert "rebase" not in row.remediation.lower()


def test_no_worktrees_is_not_applicable(repo: Repo) -> None:
    _commit(repo.root, "base", 3 * _DAY)
    assert _verdict(repo)[0] is Verdict.NOT_APPLICABLE


def _own(repo: Repo, tree: Path) -> Row:
    return {r.id: r for r in run_audit(tree, concern="agents", env=repo.env).rows}["agents.worktrees-in-sync"]


def test_the_main_checkout_has_no_worktree_of_its_own_to_judge(repo: Repo) -> None:
    _commit(repo.root, "base", 3 * _DAY)
    _worktree(repo, "elsewhere")
    assert _own(repo, repo.root).verdict is Verdict.NOT_APPLICABLE


def test_a_worktree_judges_only_itself_and_the_agent_fixes_it(repo: Repo) -> None:
    _commit(repo.root, "base", 3 * _DAY)
    tree = _worktree(repo, "mine")
    _commit(tree, "work", 2 * _DAY)
    other = _worktree(repo, "theirs")
    _commit(other, "old", 2 * _DAY)
    row = _own(repo, tree)
    assert row.verdict is Verdict.FAILING
    assert "mine" in row.evidence
    assert "theirs" not in row.evidence
    assert row.fixed_by is FixedBy.AGENT


def test_a_fresh_worktree_passes_whatever_the_others_are_doing(repo: Repo) -> None:
    _commit(repo.root, "base", 3 * _DAY)
    tree = _worktree(repo, "mine")
    _commit(tree, "work", 3600)
    other = _worktree(repo, "theirs")
    _commit(other, "old", 2 * _DAY)
    assert _own(repo, tree).verdict is Verdict.PASSING


def test_the_audit_list_leaves_this_worktrees_own_branch_out(repo: Repo) -> None:
    _commit(repo.root, "base", 3 * _DAY)
    tree = _worktree(repo, "mine")
    _commit(tree, "work", 2 * _DAY)
    other = _worktree(repo, "theirs")
    _commit(other, "old", 2 * _DAY)
    row = {r.id: r for r in run_audit(tree, concern="agents", env=repo.env).rows}["agents.other-worktrees"]
    assert row.verdict is Verdict.FAILING
    assert "theirs" in row.evidence
    assert "mine" not in row.evidence
    assert row.fixed_by is FixedBy.OWNER


def test_a_stale_local_main_does_not_fail_a_worktree_already_merged_into_origin_main(repo: Repo) -> None:
    _commit(repo.root, "base", 3 * _DAY)
    tree = _worktree(repo, "mine")
    _commit(tree, "work", 2 * _DAY)
    tip = repo.git("rev-parse", "mine").strip()
    repo.git("update-ref", "refs/remotes/origin/main", tip)
    assert _own(repo, tree).verdict is Verdict.PASSING


def test_without_origin_main_the_local_main_is_the_base(repo: Repo) -> None:
    _commit(repo.root, "base", 3 * _DAY)
    tree = _worktree(repo, "mine")
    _commit(tree, "work", 2 * _DAY)
    assert _own(repo, tree).verdict is Verdict.FAILING


def test_the_pre_push_run_does_not_count_unmerged_work_against_the_push_that_lands_it(repo: Repo) -> None:
    _commit(repo.root, "base", 3 * _DAY)
    tree = _worktree(repo, "mine")
    _commit(tree, "work", 2 * _DAY)
    assert _own(repo, tree).verdict is Verdict.FAILING  # an ordinary audit still says: land this
    pushing = {**repo.env, "PRE_COMMIT_TO_REF": "abc123"}  # what prek sets while it runs the pre-push hooks
    row = {r.id: r for r in run_audit(tree, concern="agents", env=pushing).rows}["agents.worktrees-in-sync"]
    assert row.verdict is Verdict.PASSING


def test_the_pre_push_run_still_fails_a_worktree_behind_main(repo: Repo) -> None:
    _commit(repo.root, "base", 3 * _DAY)
    tree = _worktree(repo, "mine")
    _commit(repo.root, "main-moved", 2 * _DAY)
    pushing = {**repo.env, "PRE_COMMIT_TO_REF": "abc123"}
    row = {r.id: r for r in run_audit(tree, concern="agents", env=pushing).rows}["agents.worktrees-in-sync"]
    assert row.verdict is Verdict.FAILING
    assert "behind main" in row.evidence


def test_a_worktree_in_the_middle_of_merging_main_is_not_held_for_the_commits_it_is_taking(repo: Repo) -> None:
    _commit(repo.root, "base", 3 * _DAY)
    tree = _worktree(repo, "mine")
    _commit(tree, "work", 3600)
    _commit(repo.root, "main-moved", 2 * _DAY)
    assert "behind main" in _own(repo, tree).evidence  # before the merge: failing, and it says how to fix it
    subprocess.run(["git", "merge", "--no-commit", "--no-ff", "main"], cwd=tree, check=True, capture_output=True)
    assert (tree / "main-moved").is_file()
    merging = _own(repo, tree)
    assert merging.verdict is Verdict.PASSING
    assert "merging main" in merging.evidence


def test_the_failure_names_the_merge_main_fix_for_a_branch_behind_and_the_landing_fix_for_unmerged_work(repo: Repo) -> None:
    _commit(repo.root, "base", 3 * _DAY)
    tree = _worktree(repo, "mine")
    _commit(tree, "work", 2 * _DAY)
    _commit(repo.root, "main-moved", 2 * _DAY)
    row = _own(repo, tree)
    assert row.verdict is Verdict.FAILING
    assert "behind main since" in row.evidence
    assert "merge main: `git merge main`" in row.evidence
    assert "work unmerged since" in row.evidence
    assert "land it into main" in row.evidence


def test_unmerged_work_is_still_failing_while_a_merge_of_main_is_in_progress(repo: Repo) -> None:
    _commit(repo.root, "base", 3 * _DAY)
    tree = _worktree(repo, "mine")
    _commit(tree, "work", 2 * _DAY)
    _commit(repo.root, "main-moved", 2 * _DAY)
    subprocess.run(["git", "merge", "--no-commit", "--no-ff", "main"], cwd=tree, check=True, capture_output=True)
    row = _own(repo, tree)
    assert row.verdict is Verdict.FAILING
    assert "work unmerged since" in row.evidence
    assert "behind main" not in row.evidence
