"""The git seam of a driver that works on checkouts: two protocols, fat intent operations, typed results.

``Repo`` holds what every checkout of a repository shares (identity, history, remote, the worktree list).
``Worktree`` is one checkout: its state and the write arcs a driver takes. ``RealRepo`` (``git_porcelain.real``)
runs the git binary; ``FakeRepo`` (``git_porcelain.testing``) models the same domain state in memory. One
contract suite runs the same scenarios against both, so the fake cannot drift.

Failure has two classes. An expected condition (nothing to commit, a rebase conflict, a rejected push) is a
variant of the result union, ``match``-able; worktree removal instead raises ``WorktreeRemoveRefused``.
Infrastructure (git missing, ``index.lock`` held, no identity, not
a repository, a timeout, a revision that does not resolve) raises :class:`GitUnavailable`; no operation returns
an empty string for a failure. A precondition the caller must check first (a rebase on a tracked-dirty tree)
raises ``ValueError``: a programming error, not a git outcome.

Callers pass shas and plain ref names and get records back; argv, exit codes, ``GIT_*`` variables and ``.git``
layout stay inside the implementations. ``worktree_state`` deliberately exposes porcelain bytes for signatures;
``WorktreeRemoveRefused.reason`` exposes the diagnostic a caller can show when removal is refused.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal, Protocol

from git_porcelain.api_results import (
    BranchHeld,
    BranchTaken,
    Change,
    CommandResult,
    Conflict,
    Conflicted,
    Diff,
    Dirty,
    Health,
    HookRejected,
    LogEntry,
    MergeStarted,
    NothingToRecord,
    Offline,
    Pick,
    Pushed,
    PushResult,
    Rebased,
    RebaseResult,
    Recorded,
    RecordResult,
    Ref,
    RefEntry,
    RefMoved,
    RefRejected,
    Refs,
    RefUpdate,
    RefUpdated,
    Rejected,
    Relation,
    Released,
    RemoteRef,
    RemoteRefs,
    RemoteRejected,
    RepoIdentity,
    Sha,
    Snapshot,
    Squashed,
    SquashResult,
    StillHeld,
    Synced,
    SyncResult,
    TakeResult,
    Transient,
    Tree,
    TreeId,
    UpToDate,
    WorktreeInfo,
)
from git_porcelain.errors import GitUnavailable

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

#: Seconds a git process may run when the caller names no timeout (pushes and LFS transfers pass it on). Every call is bounded.
DEFAULT_TIMEOUT: Final = 3600.0

__all__ = [
    "DEFAULT_TIMEOUT",
    "BranchHeld",
    "BranchTaken",
    "Change",
    "CommandResult",
    "Conflict",
    "Conflicted",
    "Diff",
    "Dirty",
    "GitUnavailable",
    "Health",
    "HookRejected",
    "LogEntry",
    "MergeStarted",
    "NothingToRecord",
    "Offline",
    "Pick",
    "PushResult",
    "Pushed",
    "RebaseResult",
    "Rebased",
    "RecordResult",
    "Recorded",
    "Ref",
    "RefEntry",
    "RefMoved",
    "RefRejected",
    "RefUpdate",
    "RefUpdated",
    "Refs",
    "Rejected",
    "Relation",
    "Released",
    "RemoteRef",
    "RemoteRefs",
    "RemoteRejected",
    "Repo",
    "RepoIdentity",
    "Sha",
    "Snapshot",
    "SquashResult",
    "Squashed",
    "StillHeld",
    "SyncResult",
    "Synced",
    "TakeResult",
    "Transient",
    "Tree",
    "TreeId",
    "UpToDate",
    "Worktree",
    "WorktreeInfo",
]


# -- the seam ---------------------------------------------------------------------------------------------
class Repo(Protocol):
    """What every checkout of one repository shares."""

    def tag(self, name: str, rev: str) -> None:
        """Create a lightweight tag; TagExists for an existing tag, MissingRevision for an absent object."""
        ...

    def count(self, include: Sequence[str], exclude: Sequence[str] = ()) -> int:
        """Count reachable commits minus exclusions; empty include is zero, absent revisions raise MissingRevision."""
        ...

    def refs(self, prefixes: Sequence[str]) -> tuple[RefEntry, ...]:
        """Sorted for-each-ref rows for arbitrary prefixes; empty prefixes select all. Failures raise GitUnavailable."""
        ...

    def ls_remote(self, remote: str, patterns: Sequence[str] = ()) -> RemoteRefs:
        """Advertise remote refs with tail globs and injected environment; transport failures raise GitUnavailable."""
        ...

    def is_ancestor(self, a: str, b: str) -> bool:
        """Whether a is reachable from b; missing revisions raise MissingRevision, faults raise GitReadFailure.

        Leading-dash revisions raise ValueError before invoking git.
        """
        ...

    def merge_base(self, a: str, b: str) -> Sha | None:
        """None only for missing revisions or unrelated histories; observation faults raise GitReadFailure.

        Leading-dash revisions raise ValueError before invoking git.
        """
        ...

    def cherry(self, upstream: str, head: str) -> tuple[Pick, ...]:
        """Non-merge picks in git cherry order with patch equivalence."""
        ...

    def remote_url(self, remote: str) -> str:
        """Expanded fetch URL (``insteadOf`` applied). MissingRemote only for a missing named remote."""
        ...

    def remote_push_url(self, remote: str) -> str:
        """The URL a push goes to (``remote get-url --push``: the first ``pushurl``, else ``pushInsteadOf`` or
        ``insteadOf`` over the URL). MissingRemote only for a missing named remote."""
        ...

    def remote_urls(self, remote: str) -> tuple[str, ...]:
        """Every URL, as ``remote get-url --all``, each rewritten as ``remote_url`` rewrites one: a fetch reads only the
        first ``url``. MissingRemote only for a missing named remote."""
        ...

    def remote_push_urls(self, remote: str) -> tuple[str, ...]:
        """Every URL a push goes to, as ``remote get-url --all --push``: every ``pushurl``, else every ``url``, each
        rewritten as ``remote_push_url`` rewrites one. MissingRemote only for a missing named remote."""
        ...

    def squash(self, onto: str, head: str, message: str) -> SquashResult:
        """One commit whose parent is ``onto`` and whose tree is ``head``'s changes merged onto ``onto`` (their merge
        base as the base), made in Git objects only: no checkout, index, ref or hook is touched and nothing is signed.
        ``Conflicted`` with the conflicted paths when the merge does not resolve. Author and committer are the
        repository's identity. Missing revisions raise MissingRevision, unrelated histories GitUnavailable."""
        ...

    def commit_tree(self, tree: str, parents: Sequence[str], message: str, *, when: int | None = None) -> Sha:
        """A commit of ``tree`` (a tree id, as ``Worktree.capture`` returns) with exactly these ``parents`` (revisions;
        none makes a root commit), in that order, made in Git objects only: no checkout, index, ref or hook is touched
        and nothing is signed. Author and committer are the repository's identity. With ``when`` (seconds since the epoch,
        UTC) both dates are fixed, so the same tree, parents, message and ``when`` give the same commit: a caller that
        crashed before recording the id makes it again and gets it back. Missing revisions raise MissingRevision."""
        ...

    def update_ref(self, ref: str, new: str, *, expected: str | None) -> RefUpdate:
        """Point the full ref name ``ref`` at the commit ``new`` only if it still names ``expected`` (``None``: only if
        it does not exist): ``RefUpdated``, or ``RefMoved`` with what the ref names now (``None``: nothing) and no change.
        Compare and swap in one git call, so a concurrent writer is never overwritten. A checkout that has the branch
        out keeps its old index and HEAD content: ``Worktree.reset`` brings it to the new commit."""
        ...

    def fetch(self, remote: str = "origin", *, refspecs: Sequence[str] = (), timeout: float | None = None) -> CommandResult:
        """Fetch with bounded ref-race retries, writing FETCH_HEAD; raise on final refusal."""
        ...

    def delete_remote_at(self, remote: str, ref: str, expected: Sha) -> CommandResult:
        """Lease-guarded deletion in one process; a refusal (the ref moved or is already gone) raises ``GitUnavailable``
        whose ``output`` is git's. A caller that treats "gone" as done catches it and checks ``ls_remote``."""
        ...

    def identity(self) -> RepoIdentity:
        """Canonical common dir and local key, with optional origin metadata.

        Linked worktrees share a key; independent clones differ. Only missing origin yields
        None; other origin observation faults raise GitReadFailure. Root is the common dir's
        parent when named .git, otherwise the common dir, not a selected checkout.
        RealRepo memoizes by default; disable memoization for fresh observations.
        """
        ...

    def sync(self, remote: str = "origin") -> SyncResult:
        """Fetch ``remote``; a lost ref-lock race is retried inside. ``Offline`` when it cannot be reached."""
        ...

    def relate(self, a: str, b: str) -> Relation:
        """Merge base and ahead/behind counts of two revisions, in one look."""
        ...

    def history(
        self,
        revs: Sequence[str],
        *,
        not_on: Sequence[str] = (),
        limit: int | None = None,
        patch_equivalent_to: str | None = None,
    ) -> tuple[LogEntry, ...]:
        """Commits reachable from ``revs`` and not from ``not_on``, newest first. ``patch_equivalent_to`` (one
        base) sets ``LogEntry.upstream`` by patch id."""
        ...

    def branches(self, prefix: str = "") -> tuple[tuple[str, Sha], ...]:
        """Local branches whose name starts with ``prefix``, sorted, with their tips."""
        ...

    def rename_branch(self, old: str, new: str) -> None:
        """Rename a local branch without replacing an existing branch."""
        ...

    def delete_branch(self, branch: str, *, expected: Sha) -> None:
        """Delete only at ``expected``; checked out raises ``BranchPinned``, stale tip non-retryable ``RefRace``."""
        ...

    def commit(self, rev: str) -> Sha:
        """The commit ``rev`` names, as its full id (``<rev>^{commit}``); ``MissingRevision`` when it names no commit."""
        ...

    def tree(self, rev: str) -> Tree | None:
        """The tree of a commit-ish or tree id, or of ``rev:folder`` (paths relative to that folder); None when ``rev``
        names nothing."""
        ...

    def worktrees(self, *, with_dirty: bool = False) -> tuple[WorktreeInfo, ...]:
        """Every worktree, the main one first; ``dirty`` is filled only with ``with_dirty``."""
        ...

    def add_worktree(self, path: Path, rev: str) -> Worktree:
        """A linked worktree detached at ``rev``. A registered but missing checkout refuses (``GitUnavailable``):
        ``drop_worktree`` it first."""
        ...

    def drop_worktree(self, path: Path) -> None:
        """Remove a clean, registered linked worktree (a missing folder is forgotten). ``WorktreeRemoveRefused`` with git's
        reason when it holds changes; ``NotAWorktree`` for a path git does not know. Other registrations are not pruned."""
        ...

    def discard_worktree(self, path: Path) -> None:
        """``drop_worktree`` for a checkout holding changes: they are lost (``git worktree remove --force``)."""
        ...

    def prune_worktrees(self) -> None:
        """Prune stale worktree registrations without removing live checkouts."""
        ...

    def worktree_state(self, path: Path) -> bytes | None:
        """Raw ``--no-optional-locks status --porcelain=v2 --branch -z --untracked-files=all``.
        Never memoized; None when the path is not a worktree."""
        ...

    def exclude_locally(self, patterns: Sequence[str]) -> None:
        """Append the missing ``patterns`` to the repository's ``info/exclude``."""
        ...

    def worktree(self, path: Path) -> Worktree:
        """The checkout at ``path``."""
        ...


class Worktree(Protocol):
    """One checkout: its state and the arcs a driver takes."""

    path: Path

    def stage(self, paths: Sequence[str]) -> None:
        """Stage additions, edits and deletions of these literal paths via NUL-delimited pathspecs; git refusals raise GitUnavailable."""
        ...

    def stage_pathspec(self, patterns: Sequence[str]) -> None:
        """:meth:`stage` for git pathspecs (globs and folders) instead of literal paths; git refusals raise GitUnavailable."""
        ...

    def stage_tracked(self) -> None:
        """Stage index-tracked edits/deletions (add -u); failures raise GitUnavailable."""
        ...

    def merge_ff(self, rev: str) -> None:
        """Fast-forward only; NotFastForward for divergence, MissingRevision for absence, DirtyTree for overwrite."""
        ...

    def branch(self) -> str | None:
        """Symbolic HEAD's short branch name, including unborn branches; None when detached."""
        ...

    def checkout(self, ref: str) -> None:
        """Check out an existing branch or commit-ish, preserving compatible local edits."""
        ...

    def checkout_new(self, branch: str, start: str = "HEAD") -> None:
        """Create and check out a branch exclusively; ``BranchExists`` if already present."""
        ...

    def clean(self, keep: Sequence[str] = ()) -> None:
        """Remove untracked files except keep patterns and ignored files. A symlink is removed as a link, never followed:
        nothing outside the checkout is touched, and a kept folder is left whole."""
        ...

    def clean_ignored(self, keep: Sequence[str] = ()) -> None:
        """``clean`` that removes ignored files too: with ``keep=["/.venv"]`` the reset that preserves a folder (a leading
        ``/`` anchors a pattern to the checkout root, without it a same-named folder anywhere below is kept too). A nested
        repository (a directory holding its own ``.git``) is left in place, as ``git clean -fdx`` leaves it."""
        ...

    def clean_nested(self, keep: Sequence[str] = ()) -> None:
        """``clean_ignored`` that also deletes nested repositories (``git clean -ffdx``). DESTRUCTIVE: a directory holding its
        own ``.git`` goes with its history, branches and uncommitted work, which is usually another repository's
        work, and is also a linked worktree of this repository when one sits under an ignored path (it is left
        registered but missing: call ``prune_worktrees()``). Use it only where every such directory is disposable.
        Same ``keep`` and symlink rules as ``clean``."""
        ...

    def reset(self, rev: str, *, mode: Literal["soft", "mixed", "hard"] = "mixed") -> None:
        """Move HEAD; mixed also resets the index, hard also discards tracked file edits."""
        ...

    def checkout_force(self, branch: str, start: str) -> None:
        """Create or reset a branch at start and check it out, discarding local changes."""
        ...

    @property
    def repo(self) -> Repo:
        """The repository this checkout belongs to."""
        ...

    def health(self) -> Health:
        """Is this checkout the repository it claims to be. Never memoized: it exists to catch a stray config."""
        ...

    def snapshot(self, base: str, *, inputs: Sequence[str] = ()) -> Snapshot:
        """The work as git would commit it, plus head, branch and base. ``inputs`` are literal
        paths (files or directories) included even when ignored; the real index is untouched."""
        ...

    def exclude(self, patterns: Sequence[str]) -> None:
        """Append the missing ``patterns`` (ignore-file syntax) to the ignore rules of this checkout alone: git, in
        this checkout, then treats matching untracked files as ignored (``dirty``, ``capture``, ``record``, ``clean``
        and a plain ``git status`` alike). The repository's ``info/exclude`` and every other checkout stay as they
        are. Real: a ``worktree-exclude`` file in this checkout's git directory, named by ``core.excludesFile`` in its
        ``config.worktree`` (this turns on ``extensions.worktreeConfig``); it replaces the user's global excludes file
        for this checkout."""
        ...

    def capture(self) -> TreeId:
        """The tree of this checkout's final working state: what is indexed (a path stays in even when an ignore rule
        now matches it), with every working file winning over its staged version, deletions included, and the untracked
        files that no ignore rule hides. Ignored untracked files stay out and on disk. Made in Git objects through a
        private copy of the index: the real index, HEAD, refs and working files are untouched. Unresolved merge entries
        raise UnmergedPaths and a nested repository EmbeddedRepositories; nothing is left half-made."""
        ...

    def diff(self, a: str, b: str, *, include: Sequence[str] = (), exclude: Sequence[str] = (), cap: int | None = None) -> Diff:
        """Changes and patch from tree-ish ``a`` to ``b``; ``include`` (when not empty) limits it to those literal paths, a
        folder standing for everything below it; ``exclude`` lists literal paths left out; a patch longer
        than ``cap`` characters is cut and ``truncated`` set. ``include`` with ``cap=0`` is the cheap "did any of these
        change" read: ``.changes`` is the answer."""
        ...

    def dirty(self, base: str | None = None, *, ignored_under: Sequence[str] = ()) -> Dirty:
        """Tracked and untracked changes in one read. With ``base``, also the untracked paths that base's
        ``.gitignore`` files would ignore; with ``ignored_under``, the ignored files below those prefixes (``"."`` is the
        whole checkout; a nested repository in an ignored directory is listed as that directory, with a trailing ``/``)."""
        ...

    def record(
        self,
        message: str,
        *,
        paths: Literal["own", "all", "tracked", "staged"] = "own",
        base: str | None = None,
    ) -> RecordResult:
        """Stage and commit. ``own``: tracked changes plus untracked files base's ignore rules do not cover, by
        exact path. ``all``: everything. ``tracked``: index-tracked changes, including staged additions,
        without untracked files. ``staged``: commit the existing index without staging working files.
        Hooks are skipped (``record_with_hooks`` runs them); an unchanged index gives ``NothingToRecord``
        (``record_empty`` commits anyway). To fold several commits into one, ``reset(fork, mode="soft")`` then ``record``.
        Results retain complete combined command output; infrastructure exceptions carry ``output`` too.
        Marker text is not a precondition: git decides whether the index can commit."""
        ...

    def record_with_hooks(
        self,
        message: str,
        *,
        paths: Literal["own", "all", "tracked", "staged"] = "own",
        base: str | None = None,
    ) -> RecordResult:
        """``record`` with the repository's commit hooks run; a hook's refusal returns ``HookRejected``."""
        ...

    def record_empty(self, message: str) -> RecordResult:
        """Commit the index as it is, even when it equals HEAD (``git commit --allow-empty``); hooks are skipped."""
        ...

    def amend(self, message: str = "") -> RecordResult:
        """Fold the index as it is into HEAD, even when unchanged (stage first); an empty ``message`` keeps HEAD's.
        Hooks are skipped. ``GitUnavailable`` on an unborn branch."""
        ...

    def take_branch(self, branch: str, base: str, *, clean_keep: Sequence[str] | None = None) -> TakeResult:
        """Check out ``branch`` as it is (created at ``base`` when absent). ``BranchHeld`` when another worktree holds it.
        ``clean_keep`` (not None) then deletes untracked files except those patterns."""
        ...

    def restart_branch(
        self, branch: str, base: str, *, keep_aside_as: str | None = None, clean_keep: Sequence[str] | None = None
    ) -> TakeResult:
        """Check out ``branch`` at ``base``, dropping its old tip; with ``keep_aside_as`` an old tip holding work beyond
        ``base`` is renamed to that name first (``ValueError`` when it exists). ``BranchHeld`` and ``clean_keep`` as in
        :meth:`take_branch`."""
        ...

    def release_branch(self, holder: Path) -> Released | StillHeld:
        """Free the branch ``holder`` holds: remove a clean linked worktree, else detach it there."""
        ...

    def park(self, base: str, *, clean_keep: Sequence[str] | None = None) -> Sha:
        """Detach HEAD at ``base`` (the branch stays); ``clean_keep`` as in :meth:`take_branch`. The ignored untracked
        files of now (a folder as one entry) are added to this checkout's own excludes first
        (:meth:`exclude`), so they stay ignored and on disk at ``base`` whatever its ignore rules say; when ``base``
        tracks a file among them, ``IgnoredFilesWouldBeOverwritten`` is raised and nothing changes."""
        ...

    def rebase_onto(
        self,
        base: str,
        *,
        squash_message: str | None = None,
        update_refs: bool | None = None,
    ) -> RebaseResult:
        """Replay the branch onto ``base``; with ``squash_message``, first squash a branch of more than one commit.
        A conflict leaves the rebase paused. Raises ``ValueError`` on a tracked-dirty tree or a paused rebase, and
        ``GitUnavailable`` when the squash commit fails (the original commits are restored)."""
        ...

    def rebase(self, base: str, *, update_refs: bool | None = None) -> CommandResult:
        """Resolve base to a commit OID, then invoke rebase even when up to date.

        Leading-dash bases raise ValueError; absent bases raise MissingRevision.
        Preserve every git rebase refusal and diagnostic.
        """
        ...

    def continue_rebase(self) -> CommandResult:
        """Continue using the existing index; ``ok=False`` when no rebase is paused (``rebasing()`` tells first)."""
        ...

    def resolve_and_continue(self) -> CommandResult:
        """Refuse while a conflicted file still holds markers (``ok=False``, ``conflict markers remain``), else stage
        every unmerged file and continue the paused rebase."""
        ...

    def abort_rebase(self, *, restore_to: Sha | None = None) -> CommandResult:
        """Abort, optionally restoring HEAD; idempotent: with no paused rebase (even unborn) it only restores."""
        ...

    def start_merge(self, rev: str) -> MergeStarted | UpToDate:
        """Merge commit ``rev`` into this checkout's HEAD (``--no-ff --no-commit``) and stop before the commit: clean
        merges are staged, conflicting files hold conflict markers (``MergeStarted.conflicts``), and ``rev`` is recorded
        as the merge's second parent. HEAD, the branch and every ref stay where they were. ``UpToDate`` when ``rev`` is
        already in HEAD's history (nothing started). ``ValueError`` on tracked changes, a paused rebase or a merge
        already under way; ``MissingRevision`` for an unknown ``rev``."""
        ...

    def merging(self) -> bool:
        """Whether a merge stopped by ``start_merge`` waits to be finished or aborted."""
        ...

    def finish_merge(self, message: str) -> Sha:
        """Commit the stopped merge as it is staged now: a commit with parents HEAD and the merged commit, the factory
        identity, hooks skipped, moving HEAD only (a detached checkout moves, a branch checkout moves its branch).
        Paths the caller resolved must be staged (``stage``); ``UnmergedPaths`` while the index still holds conflict
        entries, nothing is committed. ``ValueError`` with no merge under way."""
        ...

    def abort_merge(self) -> None:
        """Drop the stopped merge: HEAD, index and files return to what they were before ``start_merge``. Nothing to do
        when no merge is under way."""
        ...

    def rebasing(self) -> bool:
        """Observe both rebase backends in this checkout's git directory."""
        ...

    def unmerged(self) -> tuple[str, ...]:
        """Fresh NUL-safe unmerged paths in git order; observation faults raise GitReadFailure."""
        ...

    def push_request(
        self,
        remote: str | None,
        refspecs: Sequence[str],
        *,
        options: Sequence[str] = (),
        hook_env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> CommandResult:
        """Push supplied forms and options once, as written (``+``, ``:dst``, ``--force``, ``--delete`` are git's own)."""
        ...

    def push_refspecs(
        self,
        remote: str,
        refspecs: Sequence[str],
        *,
        hook_env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> PushResult:
        """Push explicit refs exactly as written (``+`` forces, ``:dst`` deletes); deletion-only success has an empty sha."""
        ...

    def push_lease(self, remote: str, refspec: str, *, timeout: float = DEFAULT_TIMEOUT) -> CommandResult:
        """Push with plain force-with-lease and normal hooks, without changing upstream config."""
        ...

    def lfs_push(self, remote: str, refs: Sequence[str], *, timeout: float = DEFAULT_TIMEOUT) -> CommandResult:
        """Upload all requested refs in one invocation without installing LFS or hooks."""
        ...

    def push(self, dst: str, *, remote: str = "origin", hook_env: Mapping[str, str] | None = None, head: Sha | None = None) -> PushResult:
        """Push HEAD or caller-supplied full ``head`` to ``dst``; supplying it avoids a resolution process."""
        ...

    def landed(self, base: str, title_suffix: str) -> Sha | None:
        """HEAD's sha when its subject ends with ``title_suffix`` and it is already on ``base``."""
        ...

    def grep_tracked(self, term: str) -> tuple[str, ...]:
        """Tracked text files holding ``term`` as a whole word (fixed string)."""
        ...
