"""LLM adapter protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMAdapter(Protocol):
    """A minimal completion interface. Implementations fail loud, never silent."""

    name: str

    def complete(self, prompt: str, *, model: str | None = None) -> str: ...

    def available(self) -> bool:
        """Cheap probe: is this provider usable on this machine right now?"""
        ...


__all__ = ["LLMAdapter"]
