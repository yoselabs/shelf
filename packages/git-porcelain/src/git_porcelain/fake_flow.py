"""FakeGit's multi-step writes: rebase, linked worktrees, and the remote."""

from __future__ import annotations

from typing import TYPE_CHECKING

from git_porcelain.errors import GitError
from git_porcelain.fake_merge import merge_trees, replay_list
from git_porcelain.fake_ops import hard_to, ignore_of, is_clean, switch_tree, tracked_dirty
from git_porcelain.fake_store import Rebase, WorkTree, ancestors
from git_porcelain.history import RemoteError

if TYPE_CHECKING:
    from pathlib import Path

    from git_porcelain.fake_store import Repo

__all__ = ["fetch", "push", "rebase", "rebase_abort", "worktree_add", "worktree_remove"]


def rebase(repo: Repo, wt: WorkTree, onto: str) -> bool:
    """Replay the branch onto ``onto``; False when a commit conflicted (the rebase is then stopped)."""
    head, target = repo.head_sha(wt), repo.commit_named(onto, wt)
    if wt.rebase or head is None or target is None:
        msg = "git rebase failed: no rebase possible here (stopped already, unborn HEAD, or unknown revision)"
        raise GitError(msg)
    if tracked_dirty(wt, repo.head_files(wt)):
        msg = "git rebase failed: cannot rebase: you have unstaged changes"
        raise GitError(msg)
    old = dict(repo.head_files(wt))
    if target in ancestors(repo.store, head):
        return True
    if head in ancestors(repo.store, target):
        switch_tree(repo, wt, repo.store.commits[target].files, old)
        repo.move_head(wt, target)
        return True
    orig_ref, current, files = wt.head_ref, target, dict(repo.store.commits[target].files)
    for commit in replay_list(repo, head, target):
        base = repo.store.commits[commit.parents[0]].files if commit.parents else {}
        merged, conflicts = merge_trees(repo, base, files, commit.files)
        if conflicts:
            switch_tree(repo, wt, files, old)
            wt.head_ref, wt.detached, wt.rebase = None, current, Rebase(head, orig_ref)
            _stop(repo, wt, merged, conflicts)
            return False
        if merged != files:
            current = repo.store.put_commit(merged, (current,), commit.message, repo.tick()).sha
            files = merged
    switch_tree(repo, wt, files, old)
    wt.head_ref, wt.detached = orig_ref, None if orig_ref else current
    repo.move_head(wt, current)
    return True


def _stop(repo: Repo, wt: WorkTree, merged: dict[str, str], conflicts: dict[str, bytes]) -> None:
    """Leave the checkout the way a conflicted rebase does: clean merges staged, conflicts as markers."""
    for path, sha in merged.items():
        wt.index[path] = sha
        wt.files[path] = repo.store.blobs[sha]
    for path in [p for p in wt.index if p not in merged and p not in conflicts]:
        del wt.index[path]
        wt.files.pop(path, None)
    for path, data in conflicts.items():
        wt.files[path] = data
    wt.unmerged = set(conflicts)


def rebase_abort(repo: Repo, wt: WorkTree) -> None:
    if wt.rebase is None:
        msg = "git rebase --abort exited 128: no rebase in progress"
        raise GitError(msg)
    stopped = wt.rebase
    old = dict(repo.head_files(wt))
    hard_to(repo, wt, repo.store.commits[stopped.orig_sha].files, old)
    wt.head_ref, wt.detached = stopped.orig_ref, None if stopped.orig_ref else stopped.orig_sha
    repo.move_head(wt, stopped.orig_sha)
    wt.rebase = None


def worktree_add(repo: Repo, path: Path, sha: str | None) -> WorkTree:
    """A new linked worktree at ``path``, detached at the commit."""
    if path in repo.worktrees or sha is None:
        msg = f"git worktree add exited 128: '{path}' already exists or the revision is unknown"
        raise GitError(msg)
    files = repo.store.commits[sha].files
    made = WorkTree(path, None, detached=sha, index=dict(files), files={p: repo.store.blobs[s] for p, s in files.items()})
    repo.worktrees[path] = made
    return made


def worktree_remove(repo: Repo, path: Path, *, force: bool) -> None:
    target = repo.worktrees.get(path)
    if target is None or target.main:
        msg = f"git worktree remove exited 128: '{path}' is not a linked working tree"
        raise GitError(msg)
    if not force and not target.missing and not is_clean(repo, target):
        msg = f"git worktree remove exited 128: '{path}' contains modified or untracked files, use --force to delete it"
        raise GitError(msg)
    del repo.worktrees[path]


def _remote_repo(repo: Repo, name: str) -> Repo:
    found = repo.remote_repos.get(name)
    if found is None:
        msg = f"git exited 128: '{name}' does not appear to be a git repository"
        raise RemoteError(msg, reason="other")
    return found


def fetch(repo: Repo, name: str) -> None:
    """Copy the remote's objects and set ``refs/remotes/<name>/<branch>`` for each of its branches."""
    there = _remote_repo(repo, name)
    repo.store.absorb(there.store)
    for ref, sha in there.refs.items():
        if ref.startswith("refs/heads/"):
            repo.refs[f"refs/remotes/{name}/{ref.removeprefix('refs/heads/')}"] = sha


def push(repo: Repo, wt: WorkTree, src: str, dst: str, name: str) -> None:
    """Fast-forward (or create) branch ``dst`` on the remote; a non-fast-forward is rejected, never forced."""
    there = _remote_repo(repo, name)
    sha = repo.commit_named(src, wt)
    if sha is None:
        msg = f"git push exited 1: src refspec {src} does not match any"
        raise RemoteError(msg, reason="other")
    ref = f"refs/heads/{dst}"
    there.store.absorb(repo.store)
    old = there.refs.get(ref)
    if old is not None and old not in ancestors(there.store, sha):
        msg = f"git push exited 1: ! [rejected] {src} -> {dst} (non-fast-forward)"
        raise RemoteError(msg, reason="rejected")
    there.refs[ref] = sha
    repo.refs[f"refs/remotes/{name}/{dst}"] = sha


def ignored_paths(wt: WorkTree, paths: list[str], rules: list[str]) -> set[str]:
    """The ``paths`` that ``rules`` over the checkout's ``.gitignore`` would ignore."""
    rule_set = ignore_of(wt, rules)
    return {p for p in paths if rule_set.ignores(p)}
