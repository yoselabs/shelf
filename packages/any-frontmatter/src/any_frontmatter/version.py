"""Content-hash versions of a document, and a write that refuses a stale one.

A version is SHA-256 over the document's canonical form, so a change in layout alone is
not a change: frontmatter keys are sorted, line endings become LF, and the body ends in
exactly one newline. Two files that differ only in key order or quoting share a version.

:func:`write_checked` is optimistic concurrency over a file: it writes only while the file
is still at the version the caller read, and re-checks after the rename so a writer that
slipped in between is retried rather than overwritten.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from any_frontmatter.document import Document, read, write

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path


class StaleVersionError(Exception):
    """The file is not at the version the caller expected; nothing was written.

    ``actual`` is ``None`` when the file does not exist.
    """

    def __init__(self, path: Path, expected: str, actual: str | None) -> None:
        super().__init__(f"version conflict on {path.name}")
        self.path = path
        self.expected = expected
        self.actual = actual


@dataclass(frozen=True)
class WriteOutcome:
    """Where a checked write went, and the version it left there."""

    path: Path
    version: str


def canonicalize(doc: Document) -> str:
    """``doc``'s canonical text: key-sorted JSON frontmatter, a newline, the normalized body."""
    return _canonical(doc.frontmatter, doc.body)


def version_of(frontmatter: Mapping[str, Any], body: str) -> str:
    """The version of a frontmatter mapping plus a body, with no file or document needed."""
    return hashlib.sha256(_canonical(frontmatter, body).encode("utf-8")).hexdigest()


def compute_version(doc: Document) -> str:
    """The version of ``doc``: 64 hex characters."""
    return version_of(doc.frontmatter, doc.body)


def version_of_file(path: Path) -> str:
    """The version of the file at ``path``."""
    return compute_version(read(path))


def check_version(path: Path, expected: str) -> None:
    """Raise :class:`StaleVersionError` unless the file at ``path`` is at ``expected``.

    For an operation with nothing to merge — a delete, a move — that must still refuse a
    stale caller the same way a write does.
    """
    current = version_of_file(path)
    if current != expected:
        raise StaleVersionError(path, expected, current)


def write_checked(
    path: Path,
    *,
    merge: Callable[[Document], Document],
    expected: str | None = None,
    retries: int = 2,
) -> WriteOutcome:
    """Write ``merge(current)`` to ``path``; with ``expected``, only while the file is at it.

    ``merge`` receives the document on disk (an empty one when there is no file), so a
    retry re-merges against the freshest base. ``expected=None`` writes unconditionally.
    A writer that lands between the read and the rename is retried up to ``retries``
    times; a stale ``expected`` raises :class:`StaleVersionError` and leaves the file
    untouched.
    """

    def current() -> tuple[Document, str | None]:
        if path.exists():
            doc = read(path)
            return doc, compute_version(doc)
        return Document(frontmatter={}, body=""), None

    base, base_version = current()
    if expected is None:
        new = merge(base)
        write(path, new)
        return WriteOutcome(path=path, version=compute_version(new))
    attempt = 0
    while base_version == expected:
        new = merge(base)
        write(path, new)
        version = compute_version(new)
        if version_of_file(path) == version:
            return WriteOutcome(path=path, version=version)
        attempt += 1
        if attempt > retries:
            break
        base, base_version = current()
    raise StaleVersionError(path, expected, base_version)


def _canonical(frontmatter: Mapping[str, Any], body: str) -> str:
    # `default=str` covers YAML dates and any other non-JSON scalar.
    fm = json.dumps(dict(frontmatter), sort_keys=True, ensure_ascii=False, default=str)
    normalized = body.replace("\r\n", "\n").replace("\r", "\n")
    return fm + "\n" + normalized.rstrip("\n") + "\n"
