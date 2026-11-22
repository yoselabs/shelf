"""RealGit's writes. Each is one intent: it stages, commits, switches or pushes, and says what happened as a
result variant. The English-text classification of git's complaints (a lost ref lock, a network error, a hook's
refusal) is private to this file. Every write clears the mutable memo, even when it fails half-way."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final, Literal

from git_porcelain import real_checkout, real_observe, real_read, real_remote
from git_porcelain.api import (
    BranchHeld,
    BranchTaken,
    Conflict,
    HookRejected,
    NothingToRecord,
    Offline,
    Rebased,
    Recorded,
    Released,
    Sha,
    StillHeld,
    Synced,
    UpToDate,
)
from git_porcelain.errors import IgnoredFilesWouldBeOverwritten, some
from git_porcelain.git_messages import NOT_A_HOOK
from git_porcelain.ignore_rules import literal_pattern
from git_porcelain.real_done import unavailable
from git_porcelain.remote_validation import validate_remote
from git_porcelain.revision_validation import validate_revisions

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from git_porcelain.api import (
        PushResult,
        RebaseResult,
        RecordResult,
        SyncResult,
        TakeResult,
    )
    from git_porcelain.real import RealRepo, RealWorktree
    from git_porcelain.real_done import Done

__all__ = [
    "amend",
    "exclude_locally",
    "exclude_worktree",
    "park",
    "push",
    "rebase_onto",
    "record",
    "release_branch",
    "restart_branch",
    "sync",
    "take_branch",
]

TRANSIENT: Final = re.compile(
    r"curl \d+|Broken pipe|Connection (?:reset|timed out|refused)|Could not resolve host|early EOF|RPC failed|remote end hung up|"
    r"SSL_ERROR|TLS|Operation timed out|Network is unreachable|Temporary failure in name resolution|error: 5\d\d|HTTP/\d(?:\.\d)? 5\d\d|"
    r"Could not read from remote repository|does not appear to be a git repository|unable to access",
    re.IGNORECASE,
)
_MARKERS: Final = re.compile(r"^(?:<<<<<<<|>>>>>>>)(?: |$)", re.MULTILINE)


def _identity_args(repo: RealRepo) -> list[str]:
    who = repo.who
    return [] if who is None else ["-c", f"user.name={who.name}", "-c", f"user.email={who.email}"]


def _done[T](repo: RealRepo, result: T) -> T:
    repo.invalidate()
    return result


# -- Repo -------------------------------------------------------------------------------------------------
def sync(repo: RealRepo, remote: str) -> SyncResult:
    validate_remote(remote)
    try:
        done = real_remote.fetch_done(repo, remote, (), repo.remote_timeout)
        return Offline(done.tail, output=done.output) if done.rc else Synced(output=done.output)
    finally:
        repo.invalidate()


def exclude_locally(repo: RealRepo, patterns: Sequence[str]) -> None:
    target = repo.identity().common_dir / "info" / "exclude"
    have: list[str] = target.read_text(encoding="utf-8").splitlines() if target.exists() else []
    missing = [p for p in dict.fromkeys(patterns) if p not in have]
    if not missing:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    keep = "\n" if have and not target.read_text(encoding="utf-8").endswith("\n") else ""
    with target.open("a", encoding="utf-8") as handle:
        handle.write(keep + "\n".join(missing) + "\n")


def exclude_worktree(wt: RealWorktree, patterns: Sequence[str]) -> None:
    target = real_read.git_dir_of(wt) / "worktree-exclude"
    text = target.read_text(encoding="utf-8") if target.exists() else ""
    have = text.splitlines()
    missing = [p for p in dict.fromkeys(patterns) if p not in have]
    if missing:
        keep = "\n" if text and not text.endswith("\n") else ""
        with target.open("a", encoding="utf-8") as handle:
            handle.write(keep + "\n".join(missing) + "\n")
    try:
        wt.run("config", "extensions.worktreeConfig", "true")
        wt.run("config", "--worktree", "core.excludesFile", str(target))
    finally:
        wt.repo.invalidate()


# -- Worktree ---------------------------------------------------------------------------------------------
def _stage(wt: RealWorktree, paths: Literal["own", "all", "tracked", "staged"], base: str | None) -> None:
    if paths == "staged":
        return
    if paths == "tracked":
        wt.run("add", "-u")
        return
    if paths == "all":
        wt.run("add", "-A")
        return
    state = real_read.dirty(wt, base, ())
    picks = [*state.tracked, *(p for p in state.untracked if p not in state.base_ignored)]
    if picks:
        wt.run("--literal-pathspecs", "add", "-A", "--pathspec-from-file=-", "--pathspec-file-nul", stdin="\0".join(picks))


def _delta(wt: RealWorktree, paths: Literal["own", "all", "tracked", "staged"], base: str | None, old: Sha | None) -> bool:
    """Stage the selected scope; whether the index now differs from HEAD."""
    _stage(wt, paths, base)
    against = str(old) if old is not None else "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    delta = wt.try_run("diff", "--cached", "--quiet", against)
    if delta.rc not in {0, 1}:
        raise unavailable(("diff",), delta)
    return delta.rc != 0


def record(
    wt: RealWorktree,
    message: str,
    *,
    paths: Literal["own", "all", "tracked", "staged"],
    base: str | None,
    hooks: bool,
    allow_empty: bool,
) -> RecordResult:
    validate_revisions(*([base] if base is not None else []))
    wt.run("rev-parse", "--git-dir")
    try:
        if not _delta(wt, paths, base, real_read.head_of(wt)) and not allow_empty:
            return NothingToRecord()
        args = ["commit", "-q", *([] if hooks else ["--no-verify"]), *(["--allow-empty"] if allow_empty else []), "-m", message]
        return _commit(wt, args, hooks=hooks)
    finally:
        wt.repo.invalidate()


def amend(wt: RealWorktree, message: str) -> RecordResult:
    """Fold the index into HEAD, even when it is unchanged; an empty message keeps HEAD's."""
    wt.run("rev-parse", "--git-dir")
    try:
        args = ["commit", "-q", "--no-verify", "--amend", *(["-m", message] if message else ["--no-edit"])]
        return _commit(wt, args, hooks=False)
    finally:
        wt.repo.invalidate()


def _commit(wt: RealWorktree, args: list[str], *, hooks: bool) -> RecordResult:
    done = wt.repo.try_run(wt.path, *_identity_args(wt.repo), *args)
    if done.rc != 0:
        return record_failure(args, done, hooks=hooks)
    return Recorded(some(real_read.head_of(wt)), output=done.output)


def record_failure(args: Sequence[str], done: Done, *, hooks: bool) -> RecordResult:
    """Keep complete command diagnostics, including hooks that never name themselves."""
    output = done.output
    if hooks and _hook_rejection(output):
        return HookRejected(output, output=output)
    raise unavailable(args, done, full_output=True)


def _hook_rejection(output: str) -> bool:
    if NOT_A_HOOK.search(output):
        return False
    if re.search(r"\b(?:pre-commit|prepare-commit-msg|commit-msg|post-commit)\b", output, re.IGNORECASE):
        return True
    if re.search(r"\bhook\b", output, re.IGNORECASE) and re.search(r"\b(?:declined|failed|rejected)\b", output, re.IGNORECASE):
        return True
    if re.search(r"^(?:fatal:|error:|warning:|hint:|git:)", output, re.MULTILINE | re.IGNORECASE):
        return False
    # Git prefixes diagnostics and indents status details; hooks may print their own refusal verbatim.
    git_line = re.compile(
        r"^(?:fatal:|error:|warning:|hint:|git:|On branch |Changes |Unmerged |Untracked |Your branch |"
        r"You are |nothing |no changes |Aborting|\s|#)",
        re.IGNORECASE,
    )
    return any(line and not git_line.match(line) for line in output.splitlines())


def _clean(wt: RealWorktree, clean_keep: Sequence[str] | None) -> None:
    if clean_keep is not None:
        real_checkout.clean(wt, clean_keep)


def _same(a: Path, b: Path) -> bool:
    return a.resolve() == b.resolve()


def _held(wt: RealWorktree, branch: str) -> BranchHeld | None:
    holders = tuple(w for w in wt.repo.worktrees() if w.branch == branch and not _same(w.path, wt.path))
    return BranchHeld(holders) if holders else None


def _check_track(wt: RealWorktree, track: str | None) -> None:
    if track is None:
        return
    validate_revisions(track)
    if wt.try_run("rev-parse", "--verify", "-q", f"refs/remotes/{track}").rc != 0:
        msg = f"track {track!r} is not a remote-tracking ref"
        raise ValueError(msg)


def _taken(wt: RealWorktree, branch: str, *, created: bool, kept: str | None) -> BranchTaken:
    up = wt.try_run("rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}")
    return BranchTaken(
        branch, some(real_read.head_of(wt)), created=created, kept_aside=kept, upstream=up.out.strip() if up.rc == 0 else None
    )


def take_branch(wt: RealWorktree, *, branch: str, base: str, clean_keep: Sequence[str] | None, track: str | None = None) -> TakeResult:
    validate_revisions(branch, base)
    _check_track(wt, track)
    if (held := _held(wt, branch)) is not None:
        return held
    base = real_checkout.resolve_commit(wt, base)
    exists = wt.try_run("rev-parse", "--verify", "-q", f"refs/heads/{branch}").rc == 0
    try:
        wt.run("checkout", "-q", branch, "--") if exists else wt.run("checkout", "-q", "-b", branch, "--end-of-options", base, "--")
        if track is not None and not exists:
            wt.run("branch", "-q", f"--set-upstream-to={track}", "--", branch)
        _clean(wt, clean_keep)
        return _taken(wt, branch, created=not exists, kept=None)
    finally:
        wt.repo.invalidate()


def restart_branch(
    wt: RealWorktree, *, branch: str, base: str, keep_aside_as: str | None, clean_keep: Sequence[str] | None, track: str | None = None
) -> TakeResult:
    validate_revisions(branch, base)
    _check_track(wt, track)
    if (held := _held(wt, branch)) is not None:
        return held
    base = real_checkout.resolve_commit(wt, base)
    exists = wt.try_run("rev-parse", "--verify", "-q", f"refs/heads/{branch}").rc == 0
    kept: str | None = None
    try:
        if exists and keep_aside_as is not None and int(wt.run("rev-list", "--count", f"{base}..{branch}").out) > 0:
            if wt.try_run("rev-parse", "--verify", "-q", f"refs/heads/{keep_aside_as}").rc == 0:
                msg = f"keep_aside_as {keep_aside_as!r} already exists"
                raise ValueError(msg)
            wt.run("branch", "-m", "--", branch, keep_aside_as)
            kept = keep_aside_as
        wt.run("checkout", "-q", "-B", branch, "--end-of-options", base, "--")
        if track is not None:
            wt.run("branch", "-q", f"--set-upstream-to={track}", "--", branch)
        _clean(wt, clean_keep)
        return _taken(wt, branch, created=not exists or kept is not None, kept=kept)
    finally:
        wt.repo.invalidate()


def release_branch(wt: RealWorktree, holder: Path) -> Released | StillHeld:
    info = next((w for w in wt.repo.worktrees() if _same(w.path, holder)), None)
    if info is None or _same(holder, wt.path):
        msg = f"{holder} is not another worktree of this repository"
        raise ValueError(msg)
    if info.is_main:
        return StillHeld(holder, "the main checkout holds it")
    other = wt.repo.worktree(holder)
    try:
        if not real_read.dirty(other, None, ()).raw and wt.try_run("worktree", "remove", str(holder)).rc == 0:
            return Released(holder, "removed")
        done = other.try_run("checkout", "-q", "--detach")
        return Released(holder, "detached") if done.rc == 0 else StillHeld(holder, done.tail)
    finally:
        wt.repo.invalidate()


def _keep_ignored(wt: RealWorktree, base: str) -> None:
    listed = wt.run("ls-files", "-z", "-o", "-i", "--exclude-standard", "--directory").out
    ignored = sorted(p for p in listed.split("\0") if p)
    if not ignored:
        return
    tracked = [p for p in wt.run("ls-tree", "-r", "-z", "--name-only", "--end-of-options", base).out.split("\0") if p]
    clash = tuple(i for i in ignored if any(t == i or (i.endswith("/") and t.startswith(i)) for t in tracked))
    if clash:
        msg = f"{base} tracks files that are ignored here and would be overwritten: {', '.join(clash)}"
        raise IgnoredFilesWouldBeOverwritten(msg, clash)
    exclude_worktree(wt, [literal_pattern(p) for p in ignored])


def park(wt: RealWorktree, base: str, clean_keep: Sequence[str] | None) -> Sha:
    try:
        _keep_ignored(wt, real_checkout.resolve_commit(wt, base))
        wt.run("checkout", "-q", "--detach", base)
        _clean(wt, clean_keep)
    finally:
        wt.repo.invalidate()
    return some(real_read.head_of(wt))


def _paused(wt: RealWorktree) -> bool:
    gd = real_read.git_dir_of(wt)
    return (gd / "rebase-merge").is_dir() or (gd / "rebase-apply").is_dir()


def _count(wt: RealWorktree, spec: str) -> int:
    return int(wt.run("rev-list", "--count", spec).out.strip())


def _squash_before_rebase(wt: RealWorktree, base: str, message: str, old: Sha) -> bool:
    base = real_checkout.resolve_commit(wt, base)
    fork = wt.try_run("merge-base", "--end-of-options", "HEAD", base).out.strip()
    if not fork or _count(wt, f"{fork}..HEAD") <= 1:
        return False
    wt.run("reset", "-q", "--soft", fork)
    made = wt.repo.try_run(wt.path, *_identity_args(wt.repo), "commit", "-q", "--no-verify", "--allow-empty", "-m", message)
    if made.rc == 0:
        return True
    wt.run("reset", "-q", "--hard", str(old))
    raise unavailable(("commit",), made)


def rebase_onto(
    wt: RealWorktree,
    base: str,
    squash_message: str | None,
    *,
    update_refs: bool | None = None,
) -> RebaseResult:
    validate_revisions(base)
    if _paused(wt):
        msg = "a rebase is already paused here: abort_rebase or resolve_and_continue first"
        raise ValueError(msg)
    if real_read.dirty(wt, None, ()).tracked:
        msg = "dirty: the tree has tracked changes"
        raise ValueError(msg)
    old = real_read.head_of(wt)
    if old is None:
        msg = "nothing to rebase: HEAD is unborn"
        raise ValueError(msg)
    base = real_checkout.resolve_commit(wt, base)
    if _count(wt, f"HEAD..{base}") == 0:
        return UpToDate()
    squashed = False
    try:
        if squash_message is not None:
            squashed = _squash_before_rebase(wt, base, squash_message, old)
        flags = [] if update_refs is None else ["--update-refs" if update_refs else "--no-update-refs"]
        done = wt.try_run("-c", "core.editor=true", "rebase", "-q", *flags, "--end-of-options", base)
        if done.rc == 0:
            new = real_read.head_of(wt)
            new = some(new)
            return Rebased(old, new, squashed, output=done.output)
        if _paused(wt):
            return Conflict(real_observe.unmerged(wt), done.tail, old, output=done.output)
        if squashed:
            wt.run("reset", "-q", "--hard", str(old))
        raise unavailable(("rebase",), done)
    finally:
        wt.repo.invalidate()


def has_markers(path: Path) -> bool:
    try:
        return (
            _MARKERS.search(path.read_text(encoding="utf-8", errors="replace")) is not None
        )  # lossy-ok: detect: marker search, never written back
    except OSError:
        return False


def push(wt: RealWorktree, dst: str, remote: str, hook_env: Mapping[str, str] | None, head: Sha | None = None) -> PushResult:
    """Push a pinned HEAD in two processes: rev-parse supplies the full SHA absent from porcelain.

    Pass an already known full SHA as head for a single-process typed push.
    """
    validate_remote(remote)
    if head is not None and re.fullmatch(r"[0-9a-f]{40}(?:[0-9a-f]{24})?", head) is None:
        msg = "head must be a full object id"
        raise ValueError(msg)
    head = head if head is not None else real_read.head_of(wt)
    if head is None:
        msg = "nothing to push: HEAD is unborn"
        raise ValueError(msg)
    try:
        done = wt.repo.try_run(
            wt.path,
            "push",
            "--porcelain",
            "--",
            remote,
            f"{head}:refs/heads/{dst}",
            env=hook_env,
            timeout=wt.repo.remote_timeout,
        )
    finally:
        wt.repo.invalidate()
    return real_remote.classify_push(done, head)
