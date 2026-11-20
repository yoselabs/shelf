"""git-porcelain's own error types — no dependency on any host's error taxonomy.

The host translates :class:`GitError` into its own error type at the seam (a2kay
maps it to its typed ``GitError`` for the error dispatcher). :class:`GitUnavailable` is what the
``Repo``/``Worktree`` protocols raise for infrastructure (git missing, a held ``index.lock``, no identity,
not a repository, a timeout). ``WorktreeRemoveRefused`` also inherits it for compatibility with callers
already catching removal failures, and carries the expected refusal's diagnostic separately.
"""

from __future__ import annotations

from git_porcelain.diagnostic_output import redact_output
from git_porcelain.git_messages import (
    AMBIGUOUS_REVISION,
    BRANCH_EXISTS,
    CANNOT_CHANGE_DIR,
    DIRTY_TREE,
    INDEX_LOCK,
    MERGE_NOT_MERGEABLE,
    MISSING_REVISION,
    NO_BRANCH_NAMED,
    NOT_A_REPO_HERE,
    NOT_A_REPO_MOUNT,
    NOT_A_REPO_PATH,
    NOT_FAST_FORWARD,
    PINNED,
    REF_LOCK,
    REF_RACE,
    REF_STALE,
    TAG_EXISTS,
)


class GitError(Exception):
    """A git invocation failed. ``retryable`` marks transient failures; ``hint`` is optional."""

    def __init__(self, message: str, *, retryable: bool = False, hint: str | None = None, output: str = "") -> None:
        super().__init__(redact_output(message))
        self.retryable = retryable
        self.hint = hint
        self.output = redact_output(output)


class GitUnavailable(GitError):
    """Git could not answer: ``output`` retains command diagnostics, ``retryable`` permits a later try.

    ``tail`` remains the exception's display text; invocation failures have only their failure message.
    """

    def __init__(self, message: str, *, retryable: bool = False, hint: str | None = None, output: str | None = None) -> None:
        super().__init__(message, retryable=retryable, hint=hint)
        self.output = redact_output(message if output is None else output)

    @property
    def tail(self) -> str:
        return str(self)[-600:]


class MissingRevision(GitUnavailable):
    """A revision does not identify a git object."""


class MissingRemote(GitUnavailable):
    """The requested named remote is not configured."""


class GitReadFailure(GitUnavailable):
    """An observation failed; absence cannot be inferred."""

    def __init__(
        self, message: str, *, retryable: bool = False, hint: str | None = None, output: str | None = None, push_output: str = ""
    ) -> None:
        super().__init__(message, retryable=retryable, hint=hint, output=output)
        self.push_output = redact_output(push_output)


class GitTimeout(GitUnavailable):
    """The child exceeded its deadline; distinct from a failure to invoke it."""

    def __init__(self, message: str, *, retryable: bool = False, hint: str | None = None, output: str = "") -> None:
        super().__init__(message, retryable=retryable, hint=hint, output=output)


class DirtyTree(GitUnavailable):
    """Local changes would be overwritten by the requested operation."""


class BranchExists(GitUnavailable):
    """Exclusive branch creation or rename found an existing destination."""


class TagExists(GitUnavailable):
    """Exclusive lightweight tag creation found an existing tag."""


class NotFastForward(GitUnavailable):
    """The requested merge would require a merge commit."""


class NotARepo(GitUnavailable):
    """The requested path is outside a repository or does not exist."""


class WorktreeRemoveRefused(GitUnavailable):
    """Removal was refused; ``reason`` is git's first diagnostic (or final nonempty line)."""

    def __init__(self, reason: str, *, code: int = 128, hint_line: str | None = None) -> None:
        message = f"git worktree remove exited {code}: {reason}"
        if hint_line and hint_line != reason:
            message += " | " + hint_line
        super().__init__(message)
        self.reason = reason


class PushRefused(GitError):
    """``push_refspecs`` / ``push_request`` never force or delete: the refused form is named in the message
    (``+src:dst``, ``:dst``, ``--force``, ``--delete``, ``--mirror``, ``--prune``, ``--force-with-lease``; the lease is ``push_lease``)."""


class NotAWorktree(WorktreeRemoveRefused):
    """The path is not a registered linked worktree; a caller that wants "gone is fine" catches this."""


class IndexLocked(GitUnavailable):
    """Another writer holds the index lock."""


class RefRace(GitUnavailable):
    """A ref changed since it was read, or another writer holds its lock."""


class BranchPinned(GitUnavailable):
    """A worktree has the branch checked out; ``holder`` names it."""

    def __init__(self, message: str, holder: str, *, retryable: bool = False, hint: str | None = None, output: str | None = None) -> None:
        super().__init__(message, retryable=retryable, hint=hint, output=output)
        self.holder = holder


class UnmergedPaths(GitUnavailable):
    """The index holds unresolved merge entries; ``paths`` names them."""

    def __init__(self, message: str, paths: tuple[str, ...], *, output: str | None = None) -> None:
        super().__init__(message, output=output)
        self.paths = paths


class EmbeddedRepositories(GitUnavailable):
    """The work holds a repository nested in the checkout, which git would record only as a gitlink (not its files);
    ``paths`` names them."""

    def __init__(self, message: str, paths: tuple[str, ...], *, output: str | None = None) -> None:
        super().__init__(message, output=output)
        self.paths = paths


class IgnoredFilesWouldBeOverwritten(GitUnavailable):
    """Parking would replace ignored files on disk with files the base tracks; ``paths`` names the ignored ones
    (a folder ends with ``/``). Nothing was changed."""

    def __init__(self, message: str, paths: tuple[str, ...], *, output: str | None = None) -> None:
        super().__init__(message, output=output)
        self.paths = paths


def operation_failure(stderr: str) -> type[GitUnavailable]:
    """Operation-specific refusals before the shared infrastructure classification."""
    if TAG_EXISTS.search(stderr):
        return TagExists
    if NOT_FAST_FORWARD.search(stderr):
        return NotFastForward
    return GitUnavailable


def failure(
    message: str, stderr: str, code: int, *, retryable: bool = False, hint: str | None = None, output: str | None = None
) -> GitUnavailable:
    """Translate git's specific diagnostics; an unknown failure remains ``GitUnavailable``."""
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    tail = next((line for line in lines if line.startswith(("fatal:", "error:"))), lines[-1] if lines else "")
    kind = operation_failure(stderr)
    if INDEX_LOCK.search(stderr):
        kind, retryable = IndexLocked, True
    elif match := PINNED.search(stderr):
        return BranchPinned(message, match.group(1).strip(), hint=hint, output=output)
    elif DIRTY_TREE.search(stderr):
        kind = DirtyTree
    elif BRANCH_EXISTS.search(stderr):
        kind = BranchExists
    elif NO_BRANCH_NAMED.search(stderr):
        kind = MissingRevision
    elif REF_STALE.search(stderr) or REF_RACE.search(stderr):
        kind = RefRace
        retryable = REF_LOCK.search(stderr) is not None and REF_STALE.search(stderr) is None
    elif code == 128:
        if (
            NOT_A_REPO_HERE.fullmatch(tail)
            or NOT_A_REPO_MOUNT.fullmatch(tail)
            or CANNOT_CHANGE_DIR.fullmatch(tail)
            or NOT_A_REPO_PATH.match(tail)
        ):
            kind = NotARepo
        elif MISSING_REVISION.fullmatch(tail) or AMBIGUOUS_REVISION.fullmatch(tail):
            kind = MissingRevision
    # merge reports this separately from the revision-reader diagnostics above.
    if MERGE_NOT_MERGEABLE.search(stderr):
        kind = MissingRevision
    return kind(message, retryable=retryable, hint=hint, output=output)


__all__ = [
    "BranchExists",
    "BranchPinned",
    "DirtyTree",
    "EmbeddedRepositories",
    "GitError",
    "GitReadFailure",
    "GitTimeout",
    "GitUnavailable",
    "IgnoredFilesWouldBeOverwritten",
    "IndexLocked",
    "MissingRemote",
    "MissingRevision",
    "NotARepo",
    "NotFastForward",
    "RefRace",
    "TagExists",
    "UnmergedPaths",
    "WorktreeRemoveRefused",
    "failure",
    "some",
]


def some[T](value: T | None) -> T:
    """Narrow a value git or the model must have; its absence is an internal failure."""
    if value is None:
        msg = "internal: an expected value is missing"
        raise GitUnavailable(msg)
    return value
