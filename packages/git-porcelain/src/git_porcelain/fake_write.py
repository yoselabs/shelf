"""FakeGit's writes, one function per protocol operation. Each takes the repository state and the checkout."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from git_porcelain import fake_flow as flow
from git_porcelain.api import (
    BranchHeld,
    BranchTaken,
    HookRejected,
    NothingToRecord,
    Rebased,
    Recorded,
    Released,
    Sha,
    StillHeld,
    UpToDate,
    WorktreeInfo,
)
from git_porcelain.errors import GitUnavailable, IgnoredFilesWouldBeOverwritten, some
from git_porcelain.fake_ops import (
    branch_ref,
    clean,
    ignore_of,
    is_clean,
    make_commit,
    require_index,
    stage,
    switch_tree,
    tracked_dirty,
)
from git_porcelain.fake_read import dirty, relate, resolve_commit
from git_porcelain.fake_store import ancestors
from git_porcelain.ignore_rules import literal_pattern
from git_porcelain.revision_validation import validate_revisions

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path
    from typing import Literal

    from git_porcelain.api import RebaseResult, RecordResult, TakeResult
    from git_porcelain.fake_store import CheckoutState, RepoState

__all__ = ["amend", "park", "rebase_onto", "record", "release_branch", "restart_branch", "take_branch"]


def _head(repo: RepoState, wt: CheckoutState) -> str:
    sha = repo.head_sha(wt)
    if sha is None:
        msg = "HEAD is unborn"
        raise ValueError(msg)
    return sha


def record(
    repo: RepoState,
    wt: CheckoutState,
    message: str,
    *,
    paths: Literal["own", "all", "tracked", "staged"],
    base: str | None,
    hooks: bool,
    allow_empty: bool,
) -> RecordResult:
    validate_revisions(*([base] if base is not None else []))
    old = repo.head_sha(wt)
    require_index(wt)
    record_stage(repo, wt, paths, base)
    if dict(wt.index) == (dict(repo.store.commits[old].files) if old else {}) and not allow_empty:
        return NothingToRecord()
    if (rejected := _gate(repo, hooks=hooks)) is not None:
        return rejected
    return Recorded(Sha(make_commit(repo, wt, message, (old,) if old else ())), output=repo.hooks.commit_output if hooks else "")


def amend(repo: RepoState, wt: CheckoutState, message: str) -> RecordResult:
    """Fold the index into HEAD, even when it is unchanged; an empty message keeps HEAD's."""
    old = repo.head_sha(wt)
    require_index(wt)
    if old is None:
        msg = "fatal: You have nothing to amend."
        raise GitUnavailable(msg)
    _gate(repo, hooks=False)
    previous = repo.store.commits[old]
    return Recorded(Sha(make_commit(repo, wt, message or previous.message, previous.parents)))


def _gate(repo: RepoState, *, hooks: bool) -> HookRejected | None:
    if hooks and repo.hooks.refuse_commit:
        output = repo.hooks.commit_output or "pre-commit hook declined the commit"
        return HookRejected(output, output=output)
    if repo.hooks.commit_failure is not None:
        raise GitUnavailable(repo.hooks.commit_failure)
    return None


def record_stage(repo: RepoState, wt: CheckoutState, paths: Literal["own", "all", "tracked", "staged"], base: str | None) -> None:
    """Apply the selected staging scope without committing."""
    if paths == "all":
        stage(repo, wt, None)
    elif paths == "tracked":
        stage(repo, wt, list(wt.index))
    elif paths == "own":
        state = dirty(repo, wt, base=base, ignored_under=())
        picks = [*state.tracked, *(p for p in state.untracked if p not in state.base_ignored)]
        if picks:
            stage(repo, wt, picks)


def _land(repo: RepoState, wt: CheckoutState, sha: str, ref: str | None) -> None:
    """Make HEAD point at ``ref`` (or detach at ``sha``) and the files match that commit."""
    old = dict(repo.head_files(wt))
    switch_tree(repo, wt, repo.store.commits[sha].files, old)
    wt.head_ref, wt.detached = ref, None if ref else sha


def _checkout_branch(repo: RepoState, wt: CheckoutState, ref: str, sha: str) -> None:
    """``checkout -B``: the branch moves to ``sha`` and HEAD is on it, files switched from where HEAD was."""
    old = dict(repo.head_files(wt))
    switch_tree(repo, wt, repo.store.commits[sha].files, old)
    repo.refs[ref] = sha
    wt.head_ref, wt.detached = ref, None


def _holders(repo: RepoState, wt: CheckoutState, ref: str) -> tuple[WorktreeInfo, ...]:
    return tuple(
        WorktreeInfo(w.path, Sha(h) if (h := repo.head_sha(w)) else None, ref.removeprefix("refs/heads/"), w.main, None)
        for w in repo.worktrees.values()
        if w is not wt and w.head_ref == ref
    )


def _require_remote_ref(repo: RepoState, track: str | None) -> None:
    if track is None:
        return
    validate_revisions(track)
    if f"refs/remotes/{track}" not in repo.refs:
        msg = f"track {track!r} is not a remote-tracking ref"
        raise ValueError(msg)


def _upstream_key(branch: str) -> str:
    return f"branch.{branch}.upstream"


def take_branch(
    repo: RepoState, wt: CheckoutState, *, branch: str, base: str, clean_keep: Sequence[str] | None, track: str | None = None
) -> TakeResult:
    validate_revisions(branch, base)
    _require_remote_ref(repo, track)
    ref = branch_ref(branch)
    if held := _holders(repo, wt, ref):
        return BranchHeld(held)
    target = resolve_commit(repo, wt, base)
    require_index(wt)
    exists = ref in repo.refs
    if exists:
        _land(repo, wt, repo.refs[ref], ref)
    else:
        _checkout_branch(repo, wt, ref, target)
        if track is not None:
            repo.config[_upstream_key(branch)] = track
    if clean_keep is not None:
        clean(repo, wt, clean_keep)
    return BranchTaken(branch, Sha(_head(repo, wt)), created=not exists, kept_aside=None, upstream=repo.config.get(_upstream_key(branch)))


def restart_branch(
    repo: RepoState,
    wt: CheckoutState,
    *,
    branch: str,
    base: str,
    keep_aside_as: str | None,
    clean_keep: Sequence[str] | None,
    track: str | None = None,
) -> TakeResult:
    validate_revisions(branch, base)
    _require_remote_ref(repo, track)
    ref = branch_ref(branch)
    if held := _holders(repo, wt, ref):
        return BranchHeld(held)
    target = resolve_commit(repo, wt, base)
    require_index(wt)
    exists = ref in repo.refs
    kept: str | None = None
    if exists and keep_aside_as is not None:
        ahead = ancestors(repo.store, repo.refs[ref]) - ancestors(repo.store, target)
        if ahead:
            aside = branch_ref(keep_aside_as)
            if aside in repo.refs:
                msg = f"keep_aside_as {keep_aside_as!r} already exists"
                raise ValueError(msg)
            repo.refs[aside] = repo.refs.pop(ref)
            for other in repo.worktrees.values():
                if other.head_ref == ref:
                    other.head_ref = aside
            kept = keep_aside_as
            if _upstream_key(branch) in repo.config:
                repo.config[_upstream_key(keep_aside_as)] = repo.config.pop(_upstream_key(branch))
    _checkout_branch(repo, wt, ref, target)
    if track is not None:
        repo.config[_upstream_key(branch)] = track
    if clean_keep is not None:
        clean(repo, wt, clean_keep)
    return BranchTaken(
        branch,
        Sha(_head(repo, wt)),
        created=not exists or kept is not None,
        kept_aside=kept,
        upstream=repo.config.get(_upstream_key(branch)),
    )


def release_branch(repo: RepoState, wt: CheckoutState, holder: Path) -> Released | StillHeld:
    other = repo.worktrees.get(holder)
    if other is None or other is wt:
        msg = f"{holder} is not another worktree of this repository"
        raise ValueError(msg)
    if other.main:
        return StillHeld(holder, "the main checkout holds it")
    if other.missing or is_clean(repo, other):
        flow.worktree_remove(repo, holder)
        return Released(holder, "removed")
    sha = repo.head_sha(other)
    if sha is None:
        return StillHeld(holder, "HEAD is unborn")
    _land(repo, other, sha, None)
    return Released(holder, "detached")


def _pin_ignored(repo: RepoState, wt: CheckoutState, sha: str) -> None:
    rules = ignore_of(repo, wt)
    ignored = sorted(p for p in wt.files if p not in wt.index and rules.ignores(p))
    clash = tuple(p for p in ignored if p in repo.store.commits[sha].files)
    if clash:
        msg = f"{sha} tracks files that are ignored here and would be overwritten: {', '.join(clash)}"
        raise IgnoredFilesWouldBeOverwritten(msg, clash)
    wt.exclude += [q for q in dict.fromkeys(literal_pattern(p) for p in ignored) if q not in wt.exclude]


def park(repo: RepoState, wt: CheckoutState, base: str, clean_keep: Sequence[str] | None) -> Sha:
    require_index(wt)
    sha = resolve_commit(repo, wt, base)
    _pin_ignored(repo, wt, sha)
    _land(repo, wt, sha, None)
    if clean_keep is not None:
        clean(repo, wt, clean_keep)
    return Sha(sha)


def rebase_onto(
    repo: RepoState,
    wt: CheckoutState,
    base: str,
    squash_message: str | None,
    *,
    update_refs: bool | None = None,
) -> RebaseResult:
    validate_revisions(base)
    if wt.rebase is not None:
        msg = "a rebase is already paused here: abort_rebase or resolve_and_continue first"
        raise ValueError(msg)
    if tracked_dirty(wt, repo.head_files(wt)):
        msg = "dirty: the tree has tracked changes"
        raise ValueError(msg)
    require_index(wt)
    head, target = _head(repo, wt), resolve_commit(repo, wt, base)
    if not ancestors(repo.store, target) - ancestors(repo.store, head):
        return UpToDate()
    squashed = False
    if squash_message is not None:
        fork = relate(repo, wt, "HEAD", base).merge_base
        if fork is not None and len(ancestors(repo.store, head) - ancestors(repo.store, fork)) > 1:
            if repo.hooks.squash_failure is not None:
                raise GitUnavailable(repo.hooks.squash_failure)
            repo.move_head(wt, fork)
            make_commit(repo, wt, squash_message, (fork,))
            squashed = True
    started = repo.head_sha(wt)
    started = some(started)
    updates = (
        update_refs if update_refs is not None else repo.config.get("rebase.updaterefs", "false").lower() in {"true", "yes", "on", "1"}
    )
    done = flow.start_rebase(repo, wt, started, target, update_refs=updates)
    if isinstance(done, Rebased):
        return Rebased(Sha(head), done.new_head, squashed=squashed, output=done.output)
    return replace(done, old_head=Sha(head))
