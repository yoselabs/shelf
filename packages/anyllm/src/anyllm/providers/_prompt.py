"""Shared prompt-shaping helpers used by every backend.

Factored out so the four providers do not carry byte-identical prompt-resolution
bodies — which the shelf's own intra-package body-duplication fitness test would
(correctly) reject.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anyllm.base import PromptParts


def resolve_system(system: tuple[str, ...] | str) -> str:
    """Collapse the ``system`` argument to a single string (``""`` = no system content)."""
    if isinstance(system, tuple):
        return "\n\n".join(system) if system else ""
    return system


def flat_system(parts: PromptParts | None, system: tuple[str, ...] | str) -> str:
    """Pick the system string: ``parts.system`` on the cache path, else the resolved arg."""
    if parts is not None and parts.cache_prefix != "":
        return parts.system
    return resolve_system(system)


def flat_user(parts: PromptParts | None, user: str) -> str:
    """Pick the user text: byte-stable ``prefix + tail`` on the cache path, else ``user``."""
    if parts is not None and parts.cache_prefix != "":
        return parts.cache_prefix + parts.tail
    return user


__all__ = ["flat_system", "flat_user", "resolve_system"]
