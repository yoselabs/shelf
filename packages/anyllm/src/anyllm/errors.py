"""anyllm's own error type — no dependency on any host's error taxonomy.

Adapters raise :class:`AnyLLMError`; a consuming app translates it into its own
error type at the seam (a2kay maps it to an ``LLMError``/``NoProviderError``).
"""

from __future__ import annotations


class AnyLLMError(Exception):
    """A provider failed. ``retryable`` marks transient failures; ``hint`` is optional."""

    def __init__(self, message: str, *, retryable: bool = False, hint: str | None = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.hint = hint


__all__ = ["AnyLLMError"]
