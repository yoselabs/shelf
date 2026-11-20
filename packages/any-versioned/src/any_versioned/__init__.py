"""The stored-format version check as one owner: read the version key, migrate old bodies, refuse the rest, stamp on write."""

from __future__ import annotations

from any_versioned.versioned import Migration, UnknownVersionError, Versioned

__all__ = ["Migration", "UnknownVersionError", "Versioned"]
