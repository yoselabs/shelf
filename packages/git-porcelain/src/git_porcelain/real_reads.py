"""Which git commands only read: the ones ``RealRepo(read_timeout=...)`` bounds.

A bounded read killed midway leaves nothing behind, and runs with ``GIT_OPTIONAL_LOCKS=0`` so it never takes the index
lock. Anything that writes the index, refs or files (commit, checkout, add, update-ref, ...) is not listed: killed
midway it would leave an ``index.lock``, a refusal worse than a hang. ``config`` and ``symbolic-ref`` are not listed
either: both write when given a value.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

_READS = frozenset(
    {
        "cat-file",
        "check-ignore",
        "cherry",
        "diff",
        "for-each-ref",
        "grep",
        "log",
        "ls-files",
        "ls-tree",
        "merge-base",
        "rev-list",
        "rev-parse",
        "status",
    }
)


def _subcommand(args: Sequence[str]) -> tuple[str, Sequence[str]]:
    rest = list(args)
    while rest and rest[0].startswith("-"):
        rest = rest[2:] if rest[0] == "-c" else rest[1:]
    return (rest[0], rest[1:]) if rest else ("", ())


def is_read(args: Sequence[str]) -> bool:
    name, rest = _subcommand(args)
    return name in _READS or (name == "worktree" and rest[:1] == ["list"])
