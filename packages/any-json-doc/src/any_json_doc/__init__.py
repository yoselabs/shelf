"""One JSON document per file, replaced atomically and read as one of four states.

``Doc.read()`` never guesses: a file that is there but unusable is ``Torn`` (half written, bad JSON, wrong shape, unreadable)
or ``ForeignVersion`` (another install's schema), never "empty". The caller decides; ``get`` is the lossy view for caches,
``need`` the strict one. The record type is the host's: it passes ``load`` (JSON value -> record) and ``dump`` (record -> JSON
value). ``load`` raises ``ValueError`` for a bad shape and :class:`ForeignVersionError` for a record of another version.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from atomic_io import atomic_write_json

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "Absent",
    "Doc",
    "DocSet",
    "ForeignVersion",
    "ForeignVersionError",
    "Present",
    "Read",
    "Refused",
    "Torn",
    "refusal",
]


class Refused(ValueError):  # noqa: N818 - the name task-loop's callers already catch
    """``need`` met a file that is there and cannot be read; the message names the file."""


class ForeignVersionError(ValueError):
    """Raised by a host's ``load`` for a record whose version is not the one this install reads."""

    def __init__(self, found: object, want: int) -> None:
        super().__init__(f"version {found!r}, want {want}")
        self.found = found
        self.want = want


@dataclass(frozen=True)
class Present[T]:
    rec: T


@dataclass(frozen=True)
class Absent:
    """No file (nothing was ever written, or it was deleted)."""


@dataclass(frozen=True)
class Torn:
    """A file that is there and is not a record: half written, bad JSON, a wrong shape, or unreadable."""

    path: Path
    why: str


@dataclass(frozen=True)
class ForeignVersion:
    """A record of another version (an older or newer install wrote it): never migrated, never read as empty."""

    path: Path
    found: object
    want: int


type Read[T] = Present[T] | Absent | Torn | ForeignVersion


def refusal(r: Torn | ForeignVersion) -> str:
    if isinstance(r, Torn):
        return f"{r.path} is torn or not a record of this version ({r.why}): fix or delete it; it is not read as empty"
    return f"{r.path} is v{r.found!r}, this install reads v{r.want}: delete it or run the install that wrote it"


def _same[T](value: T) -> T:
    return value


class Doc[T]:
    """One JSON document (indent 1), replaced atomically: a reader sees the old file or the new one, never half."""

    def __init__(
        self,
        path: Path,
        load: Callable[[Any], T] = _same,
        dump: Callable[[T], Any] = _same,
        *,
        fsync: bool = False,
    ) -> None:
        self.path = Path(path)
        self._load = load
        self._dump = dump
        self._fsync = fsync

    def read(self) -> Read[T]:
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return Absent()
        except (OSError, ValueError) as err:  # unreadable, or not UTF-8
            return Torn(self.path, str(err))
        try:
            return Present(self._load(json.loads(text)))
        except ForeignVersionError as err:
            return ForeignVersion(self.path, err.found, err.want)
        except ValueError as err:  # bad JSON, a host's shape refusal
            return Torn(self.path, str(err))

    def get(self) -> T | None:
        """The record, None for anything else (Absent, Torn, ForeignVersion): for files that can be derived again."""
        r = self.read()
        return r.rec if isinstance(r, Present) else None

    def need(self) -> T | None:
        """The record, None when there is no file; Refused (naming the file) when one is there and cannot be read."""
        r = self.read()
        if isinstance(r, (Torn, ForeignVersion)):
            raise Refused(refusal(r))
        return r.rec if isinstance(r, Present) else None

    def write(self, rec: T) -> None:
        atomic_write_json(self.path, self._dump(rec), indent=1, fsync=self._fsync)

    def delete(self) -> None:
        self.path.unlink(missing_ok=True)


class DocSet[T]:
    """One :class:`Doc` per key, in the file ``path_of(key)``; ``keys()`` lists the folder."""

    def __init__(
        self,
        path_of: Callable[[str], Path],
        load: Callable[[Any], T] = _same,
        dump: Callable[[T], Any] = _same,
        *,
        fsync: bool = False,
    ) -> None:
        self._path_of = path_of
        self._load = load
        self._dump = dump
        self._fsync = fsync

    def of(self, key: str) -> Doc[T]:
        return Doc(self._path_of(key), self._load, self._dump, fsync=self._fsync)

    def keys(self) -> list[str]:
        """Keys that have a file; dot-files (a writer's leftover temp) are not keys."""
        probe = self._path_of("x")
        try:
            names = [p.name for p in probe.parent.iterdir()]
        except OSError:
            return []
        return sorted(n[: -len(probe.suffix)] for n in names if n.endswith(probe.suffix) and not n.startswith("."))
