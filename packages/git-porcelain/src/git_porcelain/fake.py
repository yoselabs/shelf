"""``FakeGit``: the :class:`~git_porcelain.api.Git` protocol held in memory. No subprocess, no disk.

Refs, objects, index, files, config, worktrees and remotes live in Python objects; objects are hashed the
way git hashes them. ``tests/features/git_contract.feature`` runs the same scenarios against this and
against ``RealGit``, so a behaviour here is one real git showed. What is not modelled (see the contract):
hooks, signing, rename detection in a diff, ``.gitignore`` below the root, merges that are not a rebase,
and the author identity of a commit.

Arranging a test: ``FakeGit.init`` / ``FakeGit.clone`` make a repository, ``write_file`` / ``remove_file``
play the editor, ``set_config`` and ``add_remote`` play ``git config`` and ``git remote add``.
"""

from __future__ import annotations

from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Self

from git_porcelain import fake_flow as flow
from git_porcelain import fake_ops as ops
from git_porcelain.api import FileStat, Git, ResetMode, Worktree
from git_porcelain.errors import GitError
from git_porcelain.fake_diff import diff_stat, diff_text, grep_files, status_entries
from git_porcelain.fake_store import Repo, WorkTree, ancestors

if TYPE_CHECKING:
    from collections.abc import Sequence

    from git_porcelain.porcelain import StatusEntry

__all__ = ["FakeGit", "FakeRemote"]


class FakeRemote:
    """A bare repository a :class:`FakeGit` can fetch from and push to."""

    def __init__(self, url: str, *, default_branch: str = "main") -> None:
        self.url = url
        self.default_branch = default_branch
        self.repo = Repo(common=Path(url))

    def branches(self) -> dict[str, str]:
        """Branch name to commit sha."""
        return {r.removeprefix("refs/heads/"): s for r, s in self.repo.refs.items() if r.startswith("refs/heads/")}


class FakeGit:
    """An in-memory git bound to one checkout path."""

    def __init__(self, repo: Repo, path: Path) -> None:
        self._repo = repo
        self._path = path

    # -- arranging a test ----------------------------------------------------------------------------
    @classmethod
    def init(cls, path: Path, *, branch: str = "main", config: dict[str, str] | None = None) -> Self:
        """``git init -b branch`` at ``path``."""
        repo = Repo(common=path, config=dict(config or {}))
        repo.worktrees[path] = WorkTree(path, ops.branch_ref(branch), main=True)
        return cls(repo, path)

    @classmethod
    def clone(cls, remote: FakeRemote, path: Path) -> Self:
        """``git clone remote path``: objects, ``origin/*``, and the remote's default branch checked out."""
        branch = remote.default_branch
        repo = Repo(common=path, remotes={"origin": remote.url}, remote_repos={"origin": remote.repo})
        wt = WorkTree(path, ops.branch_ref(branch), main=True)
        repo.worktrees[path] = wt
        flow.fetch(repo, "origin")
        tip = repo.refs.get(f"refs/remotes/origin/{branch}")
        if tip is not None:
            repo.refs[ops.branch_ref(branch)] = tip
            ops.hard_to(repo, wt, repo.store.commits[tip].files, {})
        return cls(repo, path)

    def add_remote(self, name: str, remote: FakeRemote) -> None:
        self._repo.remotes[name] = remote.url
        self._repo.remote_repos[name] = remote.repo

    def set_config(self, key: str, value: str) -> None:
        self._repo.config[key] = value

    def write_file(self, rel: str, text: str | bytes) -> None:
        self._wt().files[rel] = text.encode() if isinstance(text, str) else text

    def read_file(self, rel: str) -> str | None:
        data = self._wt().files.get(rel)
        return None if data is None else data.decode()

    def remove_file(self, rel: str) -> None:
        self._wt().files.pop(rel, None)

    def drop_checkout(self, path: Path) -> None:
        """Delete a worktree's folder behind git's back (``worktree_prune`` then forgets it)."""
        self._repo.worktrees[path].missing = True

    # -- plumbing ------------------------------------------------------------------------------------
    @property
    def path(self) -> Path:
        return self._path

    def at(self, path: Path) -> Git:
        return FakeGit(self._repo, path)

    def invalidate(self) -> None:
        """Nothing is memoized in memory."""

    def _find(self) -> WorkTree | None:
        best: WorkTree | None = None
        for wt in self._repo.worktrees.values():
            if PurePath(wt.path) in {self._path, *self._path.parents} and (best is None or len(wt.path.parts) > len(best.path.parts)):
                best = wt
        return best

    def _wt(self) -> WorkTree:
        found = self._find()
        if found is None:
            msg = f"git exited 128: fatal: not a git repository: {self._path}"
            raise GitError(msg)
        return found

    # -- reads ---------------------------------------------------------------------------------------
    def head(self) -> str | None:
        return self._repo.head_sha(self._wt())

    def resolve(self, rev: str) -> str | None:
        return self._repo.commit_named(rev, self._wt())

    def branch(self) -> str | None:
        ref = self._wt().head_ref
        return ref.removeprefix("refs/heads/") if ref else None

    def common_dir(self) -> Path:
        self._wt()
        return self._repo.common / ".git"

    def toplevel(self) -> Path:
        return self._wt().path

    def is_inside_work_tree(self) -> bool:
        return self._find() is not None

    def remote_url(self, remote: str = "origin") -> str | None:
        self._wt()
        return self._repo.remotes.get(remote)

    def config_get(self, key: str) -> str | None:
        self._wt()
        return self._repo.config.get(key)

    def tree_hash(self) -> str:
        wt, repo = self._wt(), self._repo
        files = dict(repo.head_files(wt))
        ignore = ops.ignore_of(wt)
        for path, data in wt.files.items():
            if path in files or not ignore.ignores(path):
                files[path] = repo.store.put_blob(data)
        return repo.store.put_tree({p: s for p, s in files.items() if p in wt.files})

    def status(self) -> list[StatusEntry]:
        wt = self._wt()
        return status_entries(self._repo.head_files(wt), wt, ops.ignore_of(wt))

    def unmerged(self) -> list[str]:
        return sorted(self._wt().unmerged)

    def rebase_in_progress(self) -> bool:
        return self._wt().rebase is not None

    def merge_base(self, a: str, b: str) -> str | None:
        wt, repo = self._wt(), self._repo
        left, right = repo.commit_named(a, wt), repo.commit_named(b, wt)
        if left is None or right is None:
            return None
        common = ancestors(repo.store, left) & ancestors(repo.store, right)
        return max(common, key=lambda s: repo.store.commits[s].order) if common else None

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        wt, repo = self._wt(), self._repo
        top, tip = repo.commit_named(ancestor, wt), repo.commit_named(descendant, wt)
        return top is not None and tip is not None and top in ancestors(repo.store, tip)

    def rev_list_count(self, rev_range: str) -> int:
        return len(self._repo.range_commits(rev_range, self._wt()))

    def log_subjects(self, rev_range: str, *, limit: int | None = None) -> list[str]:
        found = self._repo.range_commits(rev_range, self._wt())
        return [(c.message.splitlines() or [""])[0] for c in found[:limit]]

    def diff(self, a: str, b: str, *, exclude: Sequence[str] = ()) -> str:
        wt, repo = self._wt(), self._repo
        return diff_text(repo.tree_named(a, wt), repo.tree_named(b, wt), repo.store, exclude)

    def diff_names(self, a: str, b: str) -> list[str]:
        wt, repo = self._wt(), self._repo
        left, right = repo.tree_named(a, wt), repo.tree_named(b, wt)
        return sorted(p for p in set(left) | set(right) if left.get(p) != right.get(p))

    def diff_stat(self, a: str, b: str, *, exclude: Sequence[str] = ()) -> list[FileStat]:
        wt, repo = self._wt(), self._repo
        return diff_stat(repo.tree_named(a, wt), repo.tree_named(b, wt), repo.store, exclude)

    def show(self, rev: str, path: str) -> str | None:
        try:
            sha = self._repo.tree_named(rev, self._wt()).get(path)
        except GitError:
            return None
        return None if sha is None else self._repo.store.blobs[sha].decode()

    def ls_tree(self, rev: str) -> list[str]:
        return sorted(self._repo.tree_named(rev, self._wt()))

    def ls_files(self) -> list[str]:
        return sorted(self._wt().index)

    def grep_files(self, term: str) -> list[str]:
        return grep_files(self._wt(), term)

    def ignored(self, paths: Sequence[str], rules: Sequence[str]) -> set[str]:
        return flow.ignored_paths(self._wt(), list(paths), list(rules))

    def worktree_list(self) -> list[Worktree]:
        self._wt()
        every = self._repo.worktrees.values()
        ordered = [w for w in every if w.main] + sorted((w for w in every if not w.main), key=lambda w: w.path.name)
        return [Worktree(w.path, self._repo.head_sha(w), w.head_ref.removeprefix("refs/heads/") if w.head_ref else None) for w in ordered]

    # -- writes --------------------------------------------------------------------------------------
    def add(self, paths: Sequence[str] | None = None) -> None:
        ops.stage(self._repo, self._wt(), paths)

    def commit(self, message: str, *, allow_empty: bool = False) -> str:
        return ops.commit(self._repo, self._wt(), message, allow_empty=allow_empty)

    def _land(self, wt: WorkTree, sha: str | None, ref: str | None) -> None:
        """Make HEAD point at ``ref`` (or detach at ``sha``) and the files match that commit."""
        repo = self._repo
        old = dict(repo.head_files(wt))
        new = repo.store.commits[sha].files if sha else {}
        ops.switch_tree(repo, wt, new, old)
        wt.head_ref, wt.detached = ref, None if ref else sha

    def checkout(self, branch: str) -> None:
        wt, repo = self._wt(), self._repo
        ref = ops.branch_ref(branch)
        if ref not in repo.refs and wt.head_ref != ref:
            msg = f"git checkout exited 1: pathspec '{branch}' did not match any file(s) known to git"
            raise GitError(msg)
        ops.check_branch_free(repo, wt, ref)
        self._land(wt, repo.refs.get(ref), ref)

    def checkout_new(self, branch: str, start: str | None = None, *, reset: bool = False) -> None:
        wt, repo = self._wt(), self._repo
        ref = ops.branch_ref(branch)
        if ref in repo.refs and not reset:
            msg = f"git checkout exited 128: a branch named '{branch}' already exists"
            raise GitError(msg)
        ops.check_branch_free(repo, wt, ref)
        sha = repo.commit_named(start, wt) if start else repo.head_sha(wt)
        if start and sha is None:
            msg = f"git checkout exited 128: '{start}' is not a commit"
            raise GitError(msg)
        self._land(wt, sha, ref)
        if sha:
            repo.refs[ref] = sha

    def detach(self, rev: str = "HEAD") -> None:
        wt = self._wt()
        sha = self._repo.commit_named(rev, wt)
        if sha is None:
            msg = f"git checkout exited 128: '{rev}' is not a commit"
            raise GitError(msg)
        self._land(wt, sha, None)

    def branch_rename(self, old: str, new: str) -> None:
        repo = self._repo
        self._wt()
        src, dst = ops.branch_ref(old), ops.branch_ref(new)
        if src not in repo.refs or dst in repo.refs:
            msg = f"git branch -m exited 128: cannot rename '{old}' to '{new}'"
            raise GitError(msg)
        repo.refs[dst] = repo.refs.pop(src)
        for other in repo.worktrees.values():
            if other.head_ref == src:
                other.head_ref = dst

    def reset(self, rev: str, mode: ResetMode) -> None:
        wt, repo = self._wt(), self._repo
        sha = repo.commit_named(rev, wt)
        if sha is None:
            msg = f"git reset exited 128: ambiguous argument '{rev}'"
            raise GitError(msg)
        old = dict(repo.head_files(wt))
        repo.move_head(wt, sha)
        if mode == "hard":
            ops.hard_to(repo, wt, repo.store.commits[sha].files, old)

    def rebase(self, onto: str) -> bool:
        return flow.rebase(self._repo, self._wt(), onto)

    def rebase_abort(self) -> None:
        flow.rebase_abort(self._repo, self._wt())

    def clean(self, keep: Sequence[str] = ()) -> None:
        ops.clean(self._wt(), keep)

    def worktree_add(self, path: Path, rev: str) -> Git:
        wt = self._wt()
        flow.worktree_add(self._repo, path, self._repo.commit_named(rev, wt))
        return FakeGit(self._repo, path)

    def worktree_remove(self, path: Path, *, force: bool = False) -> None:
        self._wt()
        flow.worktree_remove(self._repo, path, force=force)

    def worktree_prune(self) -> None:
        self._wt()
        for path in [p for p, w in self._repo.worktrees.items() if w.missing and not w.main]:
            del self._repo.worktrees[path]

    def fetch(self, remote: str = "origin") -> None:
        self._wt()
        flow.fetch(self._repo, remote)

    def push(self, src: str, dst: str, remote: str = "origin") -> None:
        flow.push(self._repo, self._wt(), src, dst, remote)
