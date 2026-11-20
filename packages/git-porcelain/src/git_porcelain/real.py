"""``RealRepo`` and ``RealWorktree``: the :class:`~git_porcelain.api.Repo` / ``Worktree`` protocols over the git binary.

This file holds the constructors, the one process runner (argv, env, timeout, ``GitUnavailable`` mapping) and the
memo. The reads live in ``real_read``, the writes in ``real_write``; argv, exit codes and stderr text never leave
them. Memoization is inside: immutable answers (identity, a diff between two shas, a tree) are kept for the
process; ``worktrees`` and ``branches`` are kept until an own write or :meth:`RealRepo.invalidate`; answers that
name refs are kept while the files they come from are unchanged (``real_cache``); ``health``, ``snapshot`` and
``dirty`` are never remembered, because the working tree changes behind us.
"""

from __future__ import annotations

import time
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import stream_proc
from child_env import NotFound, find

from git_porcelain import (
    real_capture,
    real_checkout,
    real_commands,
    real_env,
    real_merge,
    real_observe,
    real_operations,
    real_read,
    real_reads,
    real_remote,
    real_squash,
    real_worktrees,
    real_write,
)
from git_porcelain.api import DEFAULT_TIMEOUT
from git_porcelain.errors import GitTimeout, GitUnavailable, NotARepo
from git_porcelain.real_done import Done, unavailable
from git_porcelain.real_trace import trace_hooks
from git_porcelain.remote_validation import validate_push

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from typing import Literal

    from git_porcelain.api import (
        CommandResult,
        Diff,
        Dirty,
        FinishResult,
        Health,
        LogEntry,
        MergeStarted,
        Pick,
        PushResult,
        RebaseResult,
        RecordResult,
        RefEntry,
        RefUpdate,
        Relation,
        Released,
        RemoteRefs,
        RepoIdentity,
        Sha,
        Snapshot,
        SquashResult,
        StillHeld,
        SyncResult,
        TakeResult,
        Tree,
        TreeId,
        UpToDate,
        WorktreeInfo,
    )
    from git_porcelain.history import Identity

__all__ = ["Done", "RealRepo", "RealWorktree", "unavailable"]


def _find_git(env: Mapping[str, str]) -> Path | None:
    try:
        return find("git", env).path
    except NotFound:
        return None


class RealRepo:
    """The git binary behind :class:`~git_porcelain.api.Repo`. ``path`` is any checkout of the repository.

    ``pins`` maps each checkout path this repo may run in (``path`` and every worktree view, keyed by the exact path
    they are opened with) to the git directory the caller verified. Every call in a pinned checkout then sets
    ``GIT_DIR`` and ``GIT_WORK_TREE`` from that value and never reads ``<checkout>/.git``, so a pointer swapped after the
    caller's check is not followed; a call in a checkout with no pin raises :class:`NotARepo` before any git process
    runs (no discovery either). ``read_timeout`` (seconds; default none) bounds every read-only command (``real_reads``): on
    expiry the command is killed and :class:`GitTimeout` raised; those commands also run with ``GIT_OPTIONAL_LOCKS=0``.
    Without ``pins``, each call reads the checkout's ``.git`` entry as it is then. ``ambient`` (required) is the
    environment every git child starts from, read once by the caller at its edge (the library never reads ``os.environ``).
    """

    def __init__(
        self,
        path: Path,
        *,
        ambient: Mapping[str, str],
        identity: Identity | None = None,
        env: Mapping[str, str] | None = None,
        memoize: bool = True,
        remote_timeout: float = 600.0,
        read_timeout: float | None = None,
        sleep: Callable[[float], None] = time.sleep,
        observer: Callable[[tuple[str, ...]], None] | None = None,
        pins: Mapping[Path, Path] | None = None,
    ) -> None:
        self.path = path
        self.pins = None if pins is None else dict(pins)
        self.who = identity
        self.extra_env = dict(env or {})
        # A snapshot of the ambient environment, taken once by the caller at its edge: no call scans it again or
        # searches PATH again.
        self._ambient = real_env.base(ambient)
        self._git = _find_git(self._ambient)
        self.memoize = memoize
        self.remote_timeout = remote_timeout
        self.read_timeout = read_timeout
        self.sleep = sleep
        self.observer = observer
        self._forever: dict[object, object] = {}
        self._mutable: dict[object, object] = {}
        self.refs_seen: dict[object, tuple[object, object]] = {}
        self.snapshots: dict[str, tuple[object, object]] = {}

    # -- the one runner --------------------------------------------------------------------------------
    def run(
        self,
        cwd: Path,
        *args: str,
        pin: bool = True,
        stdin: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> Done:
        """``git -C cwd args``. A failure raises :class:`GitUnavailable` (:meth:`try_run` leaves ``rc`` to the caller)."""
        result = self.try_run(cwd, *args, pin=pin, stdin=stdin, env=env, timeout=timeout)
        if result.rc != 0:
            raise unavailable(args, result)
        return result

    def try_run(
        self,
        cwd: Path,
        *args: str,
        pin: bool = True,
        stdin: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> Done:
        """:meth:`run` that returns the :class:`Done` of a failed command too; the caller reads ``rc``. A timeout or a
        missing git still raises."""
        pin_env = self._checkout_pin(cwd) if pin or self.pins is not None else {}
        extra = {**self.extra_env, **pin_env, **(env or {})}
        reading = self.read_timeout is not None and timeout is None and real_reads.is_read(args)
        if reading:
            timeout = self.read_timeout
            extra["GIT_OPTIONAL_LOCKS"] = "0"
        limit = DEFAULT_TIMEOUT if timeout is None else timeout
        child = {**self._ambient, **extra}
        exe = self._git
        if exe is None:
            msg = "git not found on PATH"
            raise GitUnavailable(msg, hint="install git")
        if self.observer is not None:
            self.observer(args)
        try:
            pushing = bool(args and args[0] == "push")
            context = TemporaryDirectory(prefix="git-porcelain-") if pushing else nullcontext()
            with context as trace_dir:
                trace = Path(trace_dir) / "events" if trace_dir is not None else None
                if trace is not None:
                    # Git resolves hooksPath, includes and environment overrides itself. Its child_start
                    # event proves an executable hook actually ran, even when that hook printed nothing.
                    child["GIT_TRACE2_EVENT"] = str(trace)
                argv = [*real_env.argv_prefix(cwd, pin_env), *args]
                done = stream_proc.capture_bytes(
                    [str(exe), *argv[1:]],
                    env=child,
                    timeout=limit,
                    input=None if stdin is None else stdin.encode("utf-8", "surrogateescape"),
                )
                hooks, hook_exits = trace_hooks(trace) if trace is not None else ((), ())
        except OSError as exc:
            msg = f"failed to invoke git: {exc}"
            raise GitUnavailable(msg) from exc
        if done.timed_out:
            msg = f"git {args[0] if args else ''} timed out after {limit}s"
            # lossy-ok: input: git or repo bytes read as text; a non-UTF-8 file or message becomes U+FFFD, matching git's own lossy display
            raise GitTimeout(msg, retryable=True, output=(done.out + done.err).decode("utf-8", "replace").strip())
        # lossy-ok: input: git or repo bytes read as text; a non-UTF-8 file or message becomes U+FFFD, matching git's own lossy display
        return Done(done.exit, done.out, done.err.decode("utf-8", "replace"), hooks=hooks, hook_exits=hook_exits)

    def git_dir(self, checkout: Path) -> Path | None:
        """The git directory of ``checkout``: its pin when this repo has ``pins`` (None when it has none), else what its
        ``.git`` entry names now."""
        return real_env.git_dir(checkout) if self.pins is None else self.pins.get(checkout)

    def _checkout_pin(self, cwd: Path) -> dict[str, str]:
        if self.pins is None:
            return real_env.pinned(cwd)
        found = self.pins.get(cwd)
        if found is None:
            msg = f"{cwd}: no pinned git directory"
            raise NotARepo(msg, hint="open the RealRepo with pins={checkout: git_dir} for every checkout it runs in")
        return {"GIT_DIR": str(found), "GIT_WORK_TREE": str(cwd)}

    # -- the memo --------------------------------------------------------------------------------------
    def memo[T](self, key: object, compute: Callable[[], T]) -> T:
        """``compute()`` once per ``key`` for the life of the repo object (an answer that cannot change)."""
        return self._memo(self._forever, key, compute)

    def memo_until_write[T](self, key: object, compute: Callable[[], T]) -> T:
        """``compute()`` once per ``key`` until the next :meth:`invalidate` (an answer a write can change)."""
        return self._memo(self._mutable, key, compute)

    def _memo[T](self, store: dict[object, object], key: object, compute: Callable[[], T]) -> T:
        if self.memoize and key in store:
            return store[key]  # type: ignore[return-value]  # keys are tagged by the call site
        value = compute()
        if self.memoize:
            store[key] = value
        return value

    def invalidate(self) -> None:
        """Forget the answers that can change: call it after something else (a worker, a hook, another process)
        changed the repository. An own write calls it itself."""
        self._mutable.clear()
        self.refs_seen.clear()

    # -- Repo ------------------------------------------------------------------------------------------
    def tag(self, name: str, rev: str) -> None:
        real_operations.tag(self, name, rev)

    def count(self, include: Sequence[str], exclude: Sequence[str] = ()) -> int:
        return real_operations.count(self, include, exclude)

    def refs(self, prefixes: Sequence[str]) -> tuple[RefEntry, ...]:
        return real_operations.refs(self, prefixes)

    def ls_remote(self, remote: str, patterns: Sequence[str] = ()) -> RemoteRefs:
        return real_operations.ls_remote(self, remote, patterns)

    def is_ancestor(self, a: str, b: str) -> bool:
        return real_observe.is_ancestor(self, a, b)

    def merge_base(self, a: str, b: str) -> Sha | None:
        return real_observe.merge_base(self, a, b)

    def cherry(self, upstream: str, head: str) -> tuple[Pick, ...]:
        return real_observe.cherry(self, upstream, head)

    def remote_url(self, remote: str) -> str:
        return real_observe.remote_url(self, remote)

    def remote_push_url(self, remote: str) -> str:
        return real_observe.remote_push_url(self, remote)

    def remote_urls(self, remote: str) -> tuple[str, ...]:
        return real_observe.remote_urls(self, remote)

    def remote_push_urls(self, remote: str) -> tuple[str, ...]:
        return real_observe.remote_push_urls(self, remote)

    def squash(self, onto: str, head: str, message: str) -> SquashResult:
        return real_squash.squash(self, onto, head, message)

    def commit_tree(self, tree: str, parents: Sequence[str], message: str, *, when: int | None = None) -> Sha:
        return real_capture.commit_tree(self, tree, tuple(parents), message, when=when)

    def update_ref(self, ref: str, new: str, *, expected: str | None) -> RefUpdate:
        return real_capture.update_ref(self, ref, new, expected)

    def fetch(self, remote: str = "origin", *, refspecs: Sequence[str] = (), timeout: float | None = None) -> CommandResult:
        return real_remote.fetch(self, remote, refspecs, timeout)

    def delete_remote_at(self, remote: str, ref: str, expected: Sha) -> CommandResult:
        return real_remote.delete_remote_at(self, remote, ref, expected)

    def identity(self) -> RepoIdentity:
        return real_read.identity(self)

    def sync(self, remote: str = "origin") -> SyncResult:
        return real_write.sync(self, remote)

    def relate(self, a: str, b: str) -> Relation:
        return real_read.relate(self, a, b)

    def history(
        self,
        revs: Sequence[str],
        *,
        not_on: Sequence[str] = (),
        limit: int | None = None,
        patch_equivalent_to: str | None = None,
    ) -> tuple[LogEntry, ...]:
        return real_read.history(self, revs, not_on, limit, patch_equivalent_to)

    def branches(self, prefix: str = "") -> tuple[tuple[str, Sha], ...]:
        return real_read.branches(self, prefix)

    def rename_branch(self, old: str, new: str) -> None:
        real_checkout.rename_branch(self, old, new)

    def delete_branch(self, branch: str, *, expected: Sha) -> None:
        real_checkout.delete_branch(self, branch, expected=expected)

    def commit(self, rev: str) -> Sha:
        return real_read.commit(self, rev)

    def tree(self, rev: str) -> Tree | None:
        return real_read.tree(self, rev)

    def worktrees(self, *, with_dirty: bool = False) -> tuple[WorktreeInfo, ...]:
        return real_read.worktrees(self, with_dirty=with_dirty)

    def add_worktree(self, path: Path, rev: str) -> RealWorktree:
        return real_worktrees.add_worktree(self, path, rev)

    def drop_worktree(self, path: Path) -> None:
        real_worktrees.drop_worktree(self, path)

    def discard_worktree(self, path: Path) -> None:
        real_worktrees.discard_worktree(self, path)

    def prune_worktrees(self) -> None:
        real_worktrees.prune_worktrees(self)

    def worktree_state(self, path: Path) -> bytes | None:
        return real_worktrees.worktree_state(self, path)

    def exclude_locally(self, patterns: Sequence[str]) -> None:
        real_write.exclude_locally(self, patterns)

    def worktree(self, path: Path) -> RealWorktree:
        return RealWorktree(self, path)


class RealWorktree:
    """One checkout of a :class:`RealRepo`. Cheap to make: it reads nothing until asked."""

    def __init__(self, repo: RealRepo, path: Path) -> None:
        self.repo = repo
        self.path = path

    def run(self, *args: str, pin: bool = True, stdin: str | None = None, env: Mapping[str, str] | None = None) -> Done:
        return self.repo.run(self.path, *args, pin=pin, stdin=stdin, env=env)

    def try_run(self, *args: str, pin: bool = True, stdin: str | None = None, env: Mapping[str, str] | None = None) -> Done:
        return self.repo.try_run(self.path, *args, pin=pin, stdin=stdin, env=env)

    def health(self) -> Health:
        return real_read.health(self)

    def stage(self, paths: Sequence[str]) -> None:
        real_operations.stage(self, paths)

    def stage_pathspec(self, patterns: Sequence[str]) -> None:
        real_operations.stage_pathspec(self, patterns)

    def stage_tracked(self) -> None:
        real_operations.stage_tracked(self)

    def merge_ff(self, rev: str) -> None:
        real_operations.merge_ff(self, rev)

    def branch(self) -> str | None:
        return real_checkout.branch(self)

    def checkout(self, ref: str) -> None:
        real_checkout.checkout(self, ref)

    def checkout_new(self, branch: str, start: str = "HEAD") -> None:
        real_checkout.checkout_new(self, branch, start)

    def clean(self, keep: Sequence[str] = ()) -> None:
        real_checkout.clean(self, keep)

    def clean_ignored(self, keep: Sequence[str] = ()) -> None:
        real_checkout.clean_ignored(self, keep)

    def reset(self, rev: str, *, mode: Literal["soft", "mixed", "hard"] = "mixed") -> None:
        real_checkout.reset(self, rev, mode=mode)

    def checkout_force(self, branch: str, start: str) -> None:
        real_checkout.checkout_force(self, branch, start)

    def snapshot(self, base: str, *, inputs: Sequence[str] = ()) -> Snapshot:
        return real_read.snapshot(self, base, inputs=inputs)

    def exclude(self, patterns: Sequence[str]) -> None:
        real_write.exclude_worktree(self, patterns)

    def capture(self) -> TreeId:
        return real_capture.capture(self)

    def diff(self, a: str, b: str, *, include: Sequence[str] = (), exclude: Sequence[str] = (), cap: int | None = None) -> Diff:
        return real_read.diff(self, a, b, include=tuple(include), exclude=tuple(exclude), cap=cap)

    def dirty(self, base: str | None = None, *, ignored_under: Sequence[str] = ()) -> Dirty:
        return real_read.dirty(self, base=base, ignored_under=tuple(ignored_under))

    def record(
        self,
        message: str,
        *,
        paths: Literal["own", "all", "tracked", "staged"] = "own",
        base: str | None = None,
        mode: Literal["new", "amend", "squash_to"] = "new",
        squash_to: Sha | None = None,
    ) -> RecordResult:
        return real_write.record(self, message, paths=paths, base=base, mode=mode, squash_to=squash_to, hooks=False, allow_empty=False)

    def record_with_hooks(
        self,
        message: str,
        *,
        paths: Literal["own", "all", "tracked", "staged"] = "own",
        base: str | None = None,
        mode: Literal["new", "amend", "squash_to"] = "new",
        squash_to: Sha | None = None,
    ) -> RecordResult:
        return real_write.record(self, message, paths=paths, base=base, mode=mode, squash_to=squash_to, hooks=True, allow_empty=False)

    def record_empty(self, message: str) -> RecordResult:
        return real_write.record(self, message, paths="staged", base=None, mode="new", squash_to=None, hooks=False, allow_empty=True)

    def take_branch(
        self,
        branch: str,
        base: str,
        *,
        mode: Literal["resume", "fresh", "restart"],
        keep_aside_as: str | None = None,
        clean_keep: Sequence[str] | None = None,
    ) -> TakeResult:
        return real_write.take_branch(self, branch=branch, base=base, mode=mode, keep_aside_as=keep_aside_as, clean_keep=clean_keep)

    def release_branch(self, holder: Path) -> Released | StillHeld:
        return real_write.release_branch(self, holder)

    def park(self, base: str, *, clean_keep: Sequence[str] | None = None) -> Sha:
        return real_write.park(self, base, clean_keep)

    def rebase_onto(
        self,
        base: str,
        *,
        squash_message: str | None = None,
        squash_failure: Literal["raise", "continue_unsquashed"] = "raise",
        update_refs: bool | None = None,
    ) -> RebaseResult:
        return real_write.rebase_onto(self, base, squash_message, squash_failure=squash_failure, update_refs=update_refs)

    def rebase(self, base: str, *, update_refs: bool | None = None) -> CommandResult:
        return real_commands.rebase(self, base, update_refs=update_refs)

    def start_merge(self, rev: str) -> MergeStarted | UpToDate:
        return real_merge.start_merge(self, rev)

    def merging(self) -> bool:
        return real_merge.merging(self)

    def finish_merge(self, message: str) -> Sha:
        return real_merge.finish_merge(self, message)

    def abort_merge(self) -> None:
        real_merge.abort_merge(self)

    def rebasing(self) -> bool:
        return real_observe.rebasing(self)

    def unmerged(self) -> tuple[str, ...]:
        return real_observe.unmerged(self)

    def continue_rebase(self) -> CommandResult:
        return real_commands.continue_rebase(self)

    def resolve_and_continue(self) -> CommandResult:
        return real_commands.resolve_and_continue(self)

    def abort_rebase(self, *, restore_to: Sha | None = None) -> CommandResult:
        return real_commands.abort_rebase(self, restore_to=restore_to)

    def push_request(
        self,
        remote: str | None,
        refspecs: Sequence[str],
        *,
        options: Sequence[str] = (),
        hook_env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> CommandResult:
        validate_push(remote, refspecs, options)
        return real_remote.push_request(self, remote, refspecs, options=options, hook_env=hook_env, timeout=timeout)

    def push_refspecs(
        self,
        remote: str,
        refspecs: Sequence[str],
        *,
        hook_env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> PushResult:
        validate_push(remote, refspecs)
        return real_remote.push_refspecs(self, remote, refspecs, hook_env=hook_env, timeout=timeout)

    def push_lease(self, remote: str, refspec: str, *, timeout: float = DEFAULT_TIMEOUT) -> CommandResult:
        return real_remote.push_request(self, remote, [refspec], options=["--force-with-lease"], hook_env=None, timeout=timeout)

    def lfs_push(self, remote: str, refs: Sequence[str], *, timeout: float = DEFAULT_TIMEOUT) -> CommandResult:
        return real_commands.command(self, ["lfs", "push", remote, *refs], timeout=timeout, timed_out="git lfs timed out after 60 min")

    def finish_rebase(self, action: Literal["continue", "abort"], *, restore_to: Sha | None = None) -> FinishResult:
        return real_write.finish_rebase(self, action, restore_to)

    def push(self, dst: str, *, remote: str = "origin", hook_env: Mapping[str, str] | None = None, head: Sha | None = None) -> PushResult:
        return real_write.push(self, dst, remote, hook_env, head)

    def landed(self, base: str, title_suffix: str) -> Sha | None:
        return real_read.landed(self, base, title_suffix)

    def grep_tracked(self, term: str) -> tuple[str, ...]:
        return real_read.grep_tracked(self, term)
