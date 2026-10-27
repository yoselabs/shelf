"""The ``Git`` protocol: every git operation task-loop's engine makes, as typed methods on one checkout.

``RealGit`` (``git_porcelain.real``) runs the git binary. ``FakeGit`` (``git_porcelain.testing``) keeps
refs, trees, index, config and worktrees in memory. A host depends on this protocol and gets either; one
contract suite (``tests/features/git_contract.feature``) runs the same scenarios against both, so the
fake cannot drift.

A ``Git`` is bound to one checkout. ``at(path)`` gives the same repository seen from another worktree.
A failed command raises :class:`GitError`; "not there" answers (unborn HEAD, missing config key, absent
file) return ``None``. Revisions are git's own spellings: ``HEAD``, ``HEAD~1``, a branch, ``origin/main``,
a sha, a tree sha from :meth:`Git.tree_hash`, and ``A..B`` where a range is named.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from git_porcelain.porcelain import StatusEntry

__all__ = ["FileStat", "Git", "ResetMode", "Worktree"]

ResetMode = Literal["soft", "hard"]


@dataclass(frozen=True)
class Worktree:
    """One entry of ``git worktree list``: the checkout, its commit, and its branch (None when detached)."""

    path: Path
    head: str | None
    branch: str | None


@dataclass(frozen=True)
class FileStat:
    """One line of ``git diff --numstat``."""

    path: str
    added: int
    deleted: int


class Git(Protocol):
    """The git surface of one checkout."""

    @property
    def path(self) -> Path:
        """The checkout this instance is bound to."""
        ...

    def at(self, path: Path) -> Git:
        """The same repository seen from the worktree at ``path``."""
        ...

    def invalidate(self) -> None:
        """Forget memoized answers. An implementation calls this itself after its own writes; call it after
        something else (another process, a hand edit) changed the repository."""
        ...

    # -- reads ---------------------------------------------------------------------------------------
    def head(self) -> str | None:
        """The commit HEAD names; None on an unborn branch."""
        ...

    def resolve(self, rev: str) -> str | None:
        """The commit ``rev`` names (``rev-parse --verify -q rev^{commit}``); None when it names none."""
        ...

    def branch(self) -> str | None:
        """The current branch's short name; None when HEAD is detached."""
        ...

    def common_dir(self) -> Path:
        """The git directory every worktree of this repository shares (absolute)."""
        ...

    def toplevel(self) -> Path:
        """The root of this checkout."""
        ...

    def is_inside_work_tree(self) -> bool:
        """True when the bound path is inside a work tree."""
        ...

    def remote_url(self, remote: str = "origin") -> str | None:
        """The URL of ``remote``; None when there is no such remote."""
        ...

    def config_get(self, key: str) -> str | None:
        """The value of a config key as git resolves it here; None when unset."""
        ...

    def tree_hash(self) -> str:
        """The tree git would commit now (tracked and untracked files, ignored ones left out), without
        touching the real index."""
        ...

    def status(self) -> list[StatusEntry]:
        """Every changed, staged and untracked path, one entry per file."""
        ...

    def unmerged(self) -> list[str]:
        """The paths a stopped rebase or merge left conflicted."""
        ...

    def rebase_in_progress(self) -> bool:
        """True while a rebase is stopped on a conflict."""
        ...

    def merge_base(self, a: str, b: str) -> str | None:
        """The best common ancestor of two revisions; None when they share none."""
        ...

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        """True when ``ancestor`` is reachable from ``descendant`` (or equal)."""
        ...

    def rev_list_count(self, rev_range: str) -> int:
        """How many commits ``rev_range`` (``A..B`` or one revision) holds."""
        ...

    def log_subjects(self, rev_range: str, *, limit: int | None = None) -> list[str]:
        """Commit subjects of ``rev_range``, newest first."""
        ...

    def diff(self, a: str, b: str, *, exclude: Sequence[str] = ()) -> str:
        """The unified diff from tree-ish ``a`` to ``b``; ``exclude`` lists literal paths left out."""
        ...

    def diff_names(self, a: str, b: str) -> list[str]:
        """The paths that differ between two tree-ish revisions, sorted."""
        ...

    def diff_stat(self, a: str, b: str, *, exclude: Sequence[str] = ()) -> list[FileStat]:
        """Lines added and deleted per differing path."""
        ...

    def show(self, rev: str, path: str) -> str | None:
        """The text of ``path`` at ``rev``; None when absent there."""
        ...

    def ls_tree(self, rev: str) -> list[str]:
        """Every file path at ``rev``, sorted."""
        ...

    def ls_files(self) -> list[str]:
        """Every path in the index, sorted."""
        ...

    def grep_files(self, term: str) -> list[str]:
        """Tracked text files that hold ``term`` as a whole word (fixed string); empty when none."""
        ...

    def ignored(self, paths: Sequence[str], rules: Sequence[str]) -> set[str]:
        """The ``paths`` that gitignore ``rules`` (and only those) would ignore."""
        ...

    def worktree_list(self) -> list[Worktree]:
        """Every worktree of the repository, the main one first."""
        ...

    # -- writes --------------------------------------------------------------------------------------
    def add(self, paths: Sequence[str] | None = None) -> None:
        """Stage ``paths`` literally (additions, edits, deletions); None stages everything (``add -A``)."""
        ...

    def commit(self, message: str, *, allow_empty: bool = False) -> str:
        """Commit the index without hooks; return the new sha. Nothing staged raises unless ``allow_empty``."""
        ...

    def checkout(self, branch: str) -> None:
        """Switch to an existing branch."""
        ...

    def checkout_new(self, branch: str, start: str | None = None, *, reset: bool = False) -> None:
        """Create ``branch`` at ``start`` (HEAD when None) and switch to it; ``reset`` moves an existing one."""
        ...

    def detach(self, rev: str = "HEAD") -> None:
        """Detach HEAD at ``rev``."""
        ...

    def branch_rename(self, old: str, new: str) -> None:
        """Rename a branch."""
        ...

    def reset(self, rev: str, mode: ResetMode) -> None:
        """Move HEAD (and the branch) to ``rev``; ``hard`` also makes index and files match it."""
        ...

    def rebase(self, onto: str) -> bool:
        """Replay the branch onto ``onto``. True when done; False when stopped on a conflict
        (see :meth:`rebase_in_progress`). Any other failure raises."""
        ...

    def rebase_abort(self) -> None:
        """Abandon a stopped rebase and return to where it began."""
        ...

    def clean(self, keep: Sequence[str] = ()) -> None:
        """Delete untracked, non-ignored files and folders; ``keep`` patterns are spared."""
        ...

    def worktree_add(self, path: Path, rev: str) -> Git:
        """Check out ``rev`` detached in a new worktree at ``path``; return it."""
        ...

    def worktree_remove(self, path: Path, *, force: bool = False) -> None:
        """Remove a worktree; a dirty one raises unless ``force``."""
        ...

    def worktree_prune(self) -> None:
        """Forget worktrees whose folder is gone."""
        ...

    def fetch(self, remote: str = "origin") -> None:
        """Fetch ``remote``'s branches into ``refs/remotes/<remote>/``; raises ``RemoteError``."""
        ...

    def push(self, src: str, dst: str, remote: str = "origin") -> None:
        """Push ``src`` (a branch or ``HEAD``) to branch ``dst`` on ``remote``; never forces; raises ``RemoteError``."""
        ...
