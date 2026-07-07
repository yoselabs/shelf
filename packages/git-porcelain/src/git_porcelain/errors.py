"""git-porcelain's own error type — no dependency on any host's error taxonomy.

The host translates :class:`GitError` into its own error type at the seam (a2kay
maps it to its typed ``GitError`` for the error dispatcher).
"""

from __future__ import annotations


class GitError(Exception):
    """A git invocation failed. ``retryable`` marks transient failures; ``hint`` is optional."""

    def __init__(self, message: str, *, retryable: bool = False, hint: str | None = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.hint = hint


__all__ = ["GitError"]
