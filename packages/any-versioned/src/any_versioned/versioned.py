"""A stored format's version: which versions this reader knows, how an old body becomes the current one, and the stamp."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

Migration = Callable[[dict[str, Any]], dict[str, Any]]  # Any: a stored JSON document
"""One step: the body at version N -> the body at version N + 1. It returns a new dict and must not change its argument's nested values."""


class UnknownVersionError(ValueError):
    """The stored version is missing, not a whole number, or not one this reader can read; the message lists the readable ones."""


@dataclass(frozen=True, slots=True)
class Versioned:
    """`current` is the version written; `migrations[n]` turns a version-n body into a version n+1 body.

    The readable set is every migration source plus `current`. The version sits under `key` at the top of the stored object,
    first: `stamp` puts it there, `read` takes it off.
    """

    current: int
    migrations: Mapping[int, Migration] = field(default_factory=dict)
    key: str = "version"

    def __post_init__(self) -> None:
        if self.current < 1:
            message = f"current version {self.current} must be at least 1"
            raise ValueError(message)
        sources = sorted(self.migrations)
        if sources and (sources[0] < 1 or sources != list(range(sources[0], self.current))):
            message = f"migration sources {sources} must run from one version up to {self.current - 1} with no gap"
            raise ValueError(message)

    @property
    def readable(self) -> tuple[int, ...]:
        return (*sorted(self.migrations), self.current)

    def stamp(self, body: Mapping[str, Any]) -> dict[str, Any]:  # Any: a stored JSON document
        """`body` with the current version first."""
        return {self.key: self.current, **body}

    def read(self, raw: Mapping[str, Any]) -> dict[str, Any]:  # Any: a stored JSON document, as parsed
        """The body of `raw` at the current version, the version key removed. `raw` is not changed.

        Raises UnknownVersionError when the key is absent or its value is not a readable version.
        """
        found = raw.get(self.key) if isinstance(raw, Mapping) else None
        if type(found) is not int or found not in self.readable:
            raise UnknownVersionError(self._refusal(found, present=isinstance(raw, Mapping) and self.key in raw))
        body = {k: v for k, v in raw.items() if k != self.key}
        for step in range(found, self.current):
            body = self.migrations[step](body)
        return body

    def _refusal(self, found: object, *, present: bool) -> str:
        readable = ", ".join(map(str, self.readable))
        what = f"stored version {found!r}" if present else f"no {self.key!r} version key"
        newer = " (newer than this reader: update it)" if type(found) is int and found > self.current else ""
        return f"{what}{newer}; readable: {readable}; current: {self.current}"
