"""Commits, history and the remote — the part of git a program that owns a repo needs.

A host that writes files and wants every change in history calls :func:`commit_paths`
with exactly the paths it touched: whatever else the user left staged or dirty is not
swept in. Identity is passed per call, so a machine with no ``user.name`` still commits,
and hooks are skipped, so a hook cannot silently stop history. :func:`log_grep` and
:func:`show_at` read that history back; :func:`push` and :func:`fetch` talk to the remote
and raise :class:`RemoteError` with a ``reason`` a host can act on (offline, auth,
rejected). Nothing here pulls or merges: a program that owns a working tree never lets a
merge write into it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from git_porcelain.errors import GitError
from git_porcelain.porcelain import git_returncode, run_git

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

RemoteFailure = Literal["offline", "auth", "rejected", "other"]


@dataclass(frozen=True)
class Identity:
    """A commit author or committer."""

    name: str
    email: str


@dataclass(frozen=True)
class Commit:
    """A commit as :func:`log_grep` reads it."""

    sha: str
    at: datetime
    author: Identity
    subject: str
    trailers: tuple[tuple[str, str], ...] = ()
    paths: tuple[str, ...] = field(default=())


class RemoteError(GitError):
    """A push or fetch failed. ``reason`` says what a host can do about it."""

    def __init__(self, message: str, *, reason: RemoteFailure) -> None:
        super().__init__(message, retryable=reason == "offline")
        self.reason: RemoteFailure = reason


def _identity_env(author: Identity, committer: Identity) -> dict[str, str]:
    return {
        "GIT_AUTHOR_NAME": author.name,
        "GIT_AUTHOR_EMAIL": author.email,
        "GIT_COMMITTER_NAME": committer.name,
        "GIT_COMMITTER_EMAIL": committer.email,
    }


def _message(subject: str, trailers: Iterable[tuple[str, str]]) -> str:
    lines = [f"{key}: {value}" for key, value in trailers]
    return subject if not lines else subject + "\n\n" + "\n".join(lines) + "\n"


def _known(repo: Path, paths: Sequence[str]) -> list[str]:
    """The subset of ``paths`` that exists on disk or that git already tracks."""
    tracked = set(run_git(repo, "ls-files", "-z", "--", *[f":(literal){p}" for p in paths], check=False).split("\0"))
    return [p for p in paths if p in tracked or (repo / p).exists()]


def commit_paths(
    repo: Path,
    paths: Sequence[str],
    message: str,
    *,
    author: Identity,
    committer: Identity,
    trailers: Iterable[tuple[str, str]] = (),
) -> str | None:
    """Commit the current content of exactly ``paths`` (additions, edits, deletions).

    Paths staged by anyone else stay staged and out of this commit. A path that neither
    exists nor is tracked is ignored. Returns the new commit's sha, or None when none of
    ``paths`` differs from ``HEAD``. Hooks are skipped (``--no-verify``). Raises
    :class:`GitError` when git refuses — a held ``index.lock`` included, which is never
    removed here.
    """
    known = _known(repo, list(dict.fromkeys(paths))) if paths else []
    if not known:
        return None
    specs = [f":(literal){p}" for p in known]
    run_git(repo, "add", "-A", "--", *specs)
    has_head = bool(run_git(repo, "rev-parse", "--verify", "-q", "HEAD", check=False).strip())
    if has_head:
        changed = run_git(repo, "diff", "--cached", "--name-only", "-z", "HEAD", "--", *specs, check=False)
        if not changed.strip("\0"):
            return None
    run_git(
        repo,
        "commit",
        "--no-verify",
        "--only",
        "-q",
        "-m",
        _message(message, trailers),
        "--",
        *specs,
        env=_identity_env(author, committer),
    )
    return head(repo)


def head(repo: Path) -> str:
    """The sha ``HEAD`` points at."""
    return run_git(repo, "rev-parse", "HEAD").strip()


_FIELD = "\x1f"
_RECORD = "\x1e"


def log_grep(repo: Path, pattern: str, *, limit: int = 20) -> list[Commit]:
    """Commits reachable from ``HEAD`` whose message matches ``pattern`` (extended regex,
    one line at a time — so ``^Key: value$`` matches a trailer), newest first, with the
    paths each one changed. Empty on a repo with no commits."""
    if not run_git(repo, "rev-parse", "--verify", "-q", "HEAD", check=False).strip():
        return []
    fmt = _RECORD + _FIELD.join(["%H", "%aI", "%an", "%ae", "%s", "%(trailers:only,unfold,separator=%x1d)"]) + _FIELD
    out = run_git(repo, "log", "-E", f"--grep={pattern}", f"-n{limit}", f"--format={fmt}", "--name-only", "-z", "--no-renames", "HEAD")
    commits: list[Commit] = []
    for record in out.split(_RECORD)[1:]:
        sha, at, name, email, subject, trailer_text, rest = record.split(_FIELD, 6)
        trailers = tuple(tuple(t.split(": ", 1)) for t in trailer_text.split("\x1d") if ": " in t)
        paths = tuple(p.strip("\n") for p in rest.split("\0") if p.strip("\n"))
        commits.append(
            Commit(
                sha=sha,
                at=datetime.fromisoformat(at),
                author=Identity(name, email),
                subject=subject,
                trailers=trailers,  # pyright: ignore[reportArgumentType]
                paths=paths,
            )
        )
    return commits


def show_at(repo: Path, rel: str, rev: str) -> str | None:
    """The text of ``rel`` as of ``rev``, or None when the path did not exist there."""
    try:
        return run_git(repo, "show", f"{rev}:{rel}")
    except GitError:
        return None


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    """True when ``ancestor`` is reachable from ``descendant`` (a push would fast-forward)."""
    return git_returncode(repo, "merge-base", "--is-ancestor", ancestor, descendant) == 0


def upstream(repo: Path) -> str | None:
    """The current branch's upstream (``origin/main``), or None when none is set."""
    out = run_git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}", check=False).strip()
    return out or None


_AUTH = re.compile(
    r"authentication failed|permission denied|could not read (username|password)|access denied|"
    r"invalid username or password|403|401|repository not found",
    re.IGNORECASE,
)
_REJECTED = re.compile(r"\[rejected\]|non-fast-forward|fetch first|failed to push some refs", re.IGNORECASE)
_OFFLINE = re.compile(
    r"could not resolve host|network is unreachable|connection (timed out|refused)|operation timed out|"
    r"unable to access|could not read from remote repository|does not appear to be a git repository|"
    r"timed out|temporary failure",
    re.IGNORECASE,
)


def classify_remote_failure(stderr: str) -> RemoteFailure:
    """Name what went wrong talking to a remote, from git's own words."""
    if _REJECTED.search(stderr):
        return "rejected"
    if _AUTH.search(stderr):
        return "auth"
    if _OFFLINE.search(stderr):
        return "offline"
    return "other"


def _remote(repo: Path, *args: str, timeout: float) -> None:
    try:
        run_git(repo, *args, timeout=timeout)
    except GitError as exc:
        reason = "offline" if exc.retryable else classify_remote_failure(str(exc))
        raise RemoteError(str(exc), reason=reason) from exc


def push(repo: Path, remote: str | None = None, refspec: str | None = None, *, timeout: float = 120) -> None:
    """Push the current branch to its upstream, or ``refspec`` to ``remote``. Never forces."""
    args = ["push", "--porcelain"]
    if remote is not None:
        args.append(remote)
        if refspec is not None:
            args.append(refspec)
    _remote(repo, *args, timeout=timeout)


def fetch(repo: Path, remote: str | None = None, *, timeout: float = 120) -> None:
    """Fetch the remote's refs. Never touches the working tree or the current branch."""
    _remote(repo, "fetch", "--quiet", *([remote] if remote else []), timeout=timeout)


__all__ = [
    "Commit",
    "Identity",
    "RemoteError",
    "RemoteFailure",
    "classify_remote_failure",
    "commit_paths",
    "fetch",
    "head",
    "is_ancestor",
    "log_grep",
    "push",
    "show_at",
    "upstream",
]
