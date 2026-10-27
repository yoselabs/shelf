"""RealRepo's memo and snapshot skip, counted by the processes it starts (``observer``).

Real git, real temp repositories: what a memo may skip is only known against the binary. The rule behind every
test: a skipped process must never turn into a stale answer, so each "remembered" test is paired with the change
that must make it ask git again.
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

import pytest
from git_porcelain import Identity, RealRepo, RealWorktree
from git_porcelain.testing import apply_hermetic_env
from git_porcelain.testing import git as run

if TYPE_CHECKING:
    from pathlib import Path

_ME = Identity("Cache Author", "author@example.invalid")


class Rig:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.calls: list[tuple[str, ...]] = []
        origin = self.root / "o.git"
        run(self.root, "init", "-q", "--bare", "-b", "main", str(origin))
        run(self.root, "clone", "-q", str(origin), "r")
        self.path = self.root / "r"
        self.repo = RealRepo(self.path, observer=self.calls.append)
        self.wt: RealWorktree = self.repo.worktree(self.path)
        (self.path / "a.txt").write_text("one\n", encoding="utf-8")
        self.wt.record("first", paths="all")
        self.wt.push("main")
        self.calls.clear()

    def count(self, *words: str) -> int:
        return sum(all(w in call for w in words) for call in self.calls)

    def age(self, rel: str) -> None:
        """Make the file look old, as one a worker wrote minutes ago does."""
        target = self.path / rel
        then = time.time() - 600
        os.utime(target, (then, then))


@pytest.fixture
def rig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Rig:
    apply_hermetic_env(monkeypatch, identity=_ME, home=tmp_path / "home")
    return Rig(tmp_path)


def test_identity_is_asked_of_git_once(rig: Rig) -> None:
    for _ in range(3):
        rig.repo.identity()
    assert rig.count("--git-common-dir") == 1


def test_memo_can_be_switched_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    apply_hermetic_env(monkeypatch, identity=_ME, home=tmp_path / "home")
    run(tmp_path, "init", "-q", "-b", "main", "x")
    calls: list[tuple[str, ...]] = []
    repo = RealRepo(tmp_path / "x", memoize=False, observer=calls.append)
    repo.identity()
    repo.identity()
    assert sum("--git-common-dir" in c for c in calls) == 2


def test_an_unchanged_tree_is_not_written_again(rig: Rig) -> None:
    (rig.path / "b.txt").write_text("b\n", encoding="utf-8")
    rig.age("b.txt")
    first = rig.wt.snapshot("origin/main")
    assert rig.count("write-tree") == 1
    again = rig.wt.snapshot("origin/main")
    assert again == first
    assert rig.count("write-tree") == 1
    assert rig.count("status") == 2  # the check that the work is the same is one status, never nothing


def test_an_edited_tree_is_written_again(rig: Rig) -> None:
    (rig.path / "b.txt").write_text("b\n", encoding="utf-8")
    rig.age("b.txt")
    first = rig.wt.snapshot("origin/main")
    (rig.path / "b.txt").write_text("c\n", encoding="utf-8")
    second = rig.wt.snapshot("origin/main")
    assert second.tree != first.tree
    assert rig.count("write-tree") == 2


def test_a_new_head_is_written_again_even_when_the_files_are_the_same(rig: Rig) -> None:
    first = rig.wt.snapshot("origin/main")
    assert rig.wt.record("empty", allow_empty=True).__class__.__name__ == "Recorded"
    second = rig.wt.snapshot("origin/main")
    assert second.head != first.head
    assert second.tree == first.tree
    assert rig.count("write-tree") == 2


def test_two_same_size_edits_in_one_tick_are_two_trees(rig: Rig) -> None:
    target = rig.path / "b.txt"
    target.write_text("aaaa\n", encoding="utf-8")
    first = rig.wt.snapshot("origin/main")
    before = target.stat()
    target.write_text("bbbb\n", encoding="utf-8")
    os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert target.stat().st_size == before.st_size
    assert target.stat().st_mtime_ns == before.st_mtime_ns
    assert rig.wt.snapshot("origin/main").tree != first.tree


def test_a_ref_name_answer_is_kept_until_the_ref_moves(rig: Rig) -> None:
    first = rig.repo.relate("HEAD", "origin/main")
    rig.repo.relate("HEAD", "origin/main")
    assert rig.count("merge-base") == 1
    assert rig.wt.record("ahead", allow_empty=True).__class__.__name__ == "Recorded"
    moved = rig.repo.relate("HEAD", "origin/main")
    assert (first.ahead, moved.ahead) == (0, 1)


def test_a_ref_moved_by_someone_else_is_seen(rig: Rig) -> None:
    rig.repo.relate("HEAD", "origin/main")
    run(rig.path, "-c", "user.name=o", "-c", "user.email=o@x.y", "commit", "-q", "--allow-empty", "-m", "outside")
    assert rig.repo.relate("HEAD", "origin/main").ahead == 1
    assert rig.count("merge-base") == 2


def test_an_answer_about_shas_is_kept_for_good(rig: Rig) -> None:
    head = rig.wt.snapshot("origin/main").head
    assert head is not None
    rig.calls.clear()
    for _ in range(2):
        rig.repo.relate(head, head)
        rig.wt.diff(head, head)
    assert rig.count("merge-base") == 1
    assert rig.count("--numstat") == 1


def test_branches_are_kept_until_a_branch_moves(rig: Rig) -> None:
    rig.repo.branches()
    rig.repo.branches("task/")
    assert rig.count("for-each-ref") == 1
    run(rig.path, "branch", "task/new")
    assert [name for name, _ in rig.repo.branches("task/")] == ["task/new"]
    assert rig.count("for-each-ref") == 2


def test_worktrees_are_kept_until_invalidated(rig: Rig) -> None:
    rig.repo.worktrees()
    rig.repo.worktrees()
    assert rig.count("worktree", "list") == 1
    run(rig.path, "worktree", "add", "-q", "--detach", str(rig.root / "w"), "HEAD")
    assert len(rig.repo.worktrees()) == 1
    rig.repo.invalidate()
    assert len(rig.repo.worktrees()) == 2


def test_an_own_write_clears_what_can_change(rig: Rig) -> None:
    rig.repo.worktrees()
    rig.repo.add_worktree(rig.root / "w", "HEAD")
    assert len(rig.repo.worktrees()) == 2


def test_health_is_two_processes_every_time(rig: Rig) -> None:
    rig.wt.health()
    rig.wt.health()
    assert rig.count("config") == 2
    assert rig.count("rev-parse", "--show-toplevel") == 2


def test_a_tree_lists_and_reads_once(rig: Rig) -> None:
    for _ in range(2):
        found = rig.repo.tree("HEAD")
        assert found is not None
        assert sorted(found.files) == ["a.txt"]
        assert found.read("a.txt") == b"one\n"
    assert rig.count("ls-tree") == 1
    assert rig.count("cat-file") == 1


def test_a_repository_on_the_reftable_backend_is_never_memoized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    apply_hermetic_env(monkeypatch, identity=_ME, home=tmp_path / "home")
    path = tmp_path / "t"
    run(tmp_path, "init", "-q", "-b", "main", "--ref-format=reftable", "t")
    calls: list[tuple[str, ...]] = []
    repo = RealRepo(path, observer=calls.append)
    wt = repo.worktree(path)
    (path / "a.txt").write_text("x\n", encoding="utf-8")
    wt.record("one", paths="all")
    calls.clear()
    repo.relate("HEAD", "main")
    repo.relate("HEAD", "main")
    assert sum("merge-base" in c for c in calls) == 2


def test_a_lost_ref_lock_is_retried_and_a_dead_origin_is_offline(rig: Rig) -> None:
    (rig.root / "o.git").rename(rig.root / "gone.git")
    assert rig.repo.sync().__class__.__name__ == "Offline"
    assert rig.count("fetch") == 1  # an unreachable origin is not a lock race: no retry
