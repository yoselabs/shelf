"""What a file's name and bytes say: safe names, contained paths, binary sniff, media type.

- :func:`safe_name` — a bare basename, NFC, or :class:`UnsafeNameError`.
- :func:`resolve_within` — a reference resolved under a root, or :class:`PathEscapeError`.
- :func:`looks_binary` — a NUL byte in the first 8 KiB.
- :func:`name_collision` — the existing name equal only after case folding and NFC.
- :func:`media_type` — the caller's media type, else one read off the name from a table
  this module owns. Never the host's ``/etc/mime.types``: a slim container has none, so
  ``.xlsx`` and ``.docx`` came back unknown there and were refused.
"""

from __future__ import annotations

import functools
import mimetypes
import os
import unicodedata
from pathlib import Path

from any_file._media_types import MEDIA_TYPES as _MEDIA_TYPES

_SNIFF_BYTES = 8192
OCTET_STREAM = "application/octet-stream"

#: The types Python's built-in table lacks (3.11/3.12) and a document store meets. Added to
#: an isolated table, so the answer is the same on a laptop and in ``python:3.12-slim``.
REGISTERED_TYPES: dict[str, str] = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".odp": "application/vnd.oasis.opendocument.presentation",
    ".odg": "application/vnd.oasis.opendocument.graphics",
    ".epub": "application/epub+zip",
    ".rtf": "application/rtf",
    ".jsonl": "application/x-ndjson",
    ".ndjson": "application/x-ndjson",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
    ".toml": "application/toml",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".log": "text/plain",
    ".ics": "text/calendar",
    ".vtt": "text/vtt",
    ".eml": "message/rfc822",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".weba": "audio/webm",
    ".webp": "image/webp",
    ".heif": "image/heif",
    ".heic": "image/heic",
    ".avif": "image/avif",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".bmp": "image/bmp",
    ".mkv": "video/x-matroska",
    ".m4v": "video/x-m4v",
    ".avi": "video/x-msvideo",
    ".3gp": "video/3gpp",
    ".zip": "application/zip",
    ".7z": "application/x-7z-compressed",
    **_MEDIA_TYPES,
}

#: Media types beside every ``text/*`` that decode as text.
TEXT_MEDIA_TYPES: frozenset[str] = frozenset({"application/json", "application/x-ndjson", "application/yaml", "application/toml"})


class AnyFileError(ValueError):
    """A file name or path refused; :attr:`value` is what was given."""

    def __init__(self, message: str, value: str) -> None:
        self.value = value
        super().__init__(message)


class UnsafeNameError(AnyFileError):
    """A name that is empty, ``.``/``..``, or holds a path separator."""


class PathEscapeError(AnyFileError):
    """A reference that resolves outside its root."""


def safe_name(name: str) -> str:
    """``name`` as a bare basename in NFC, or :class:`UnsafeNameError`."""
    if not name or name in {".", ".."} or "/" in name or "\\" in name or os.sep in name or (os.altsep and os.altsep in name):
        msg = f"unsafe file name: {name!r}"
        raise UnsafeNameError(msg, name)
    return unicodedata.normalize("NFC", Path(name).name)


def resolve_within(root: Path, ref: str | Path) -> Path:
    """``ref`` resolved under ``root``, refused with :class:`PathEscapeError` when it lands outside.

    ``ref`` may be relative (joined onto ``root``) or absolute; either way the fully
    resolved result must be inside the resolved ``root``.
    """
    root_resolved = root.resolve()
    candidate = Path(ref)
    resolved = (candidate if candidate.is_absolute() else root_resolved / candidate).resolve()
    if not resolved.is_relative_to(root_resolved):
        msg = f"{str(ref)!r} escapes {root_resolved}"
        raise PathEscapeError(msg, str(ref))
    return resolved


def looks_binary(data: bytes) -> bool:
    """True when the first 8 KiB hold a NUL byte, the mark of a binary file."""
    return b"\x00" in data[:_SNIFF_BYTES]


def _fold(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


def name_collision(existing: list[str], name: str) -> str | None:
    """The existing name ``name`` equals only after folding case and normalization, if any.

    An exact match is not a collision (it is the same file). Two such names are one file on
    a case-insensitive file system and two in git.
    """
    if name in existing:
        return None
    folded = _fold(name)
    return next((present for present in existing if _fold(present) == folded), None)


@functools.cache
def _table() -> mimetypes.MimeTypes:
    """Python's built-in table plus :data:`REGISTERED_TYPES`; no host file is read into it."""
    table = mimetypes.MimeTypes(filenames=())
    for ext, media in REGISTERED_TYPES.items():
        table.add_type(media, ext, strict=True)
    return table


def media_type(name: str, declared: str | None = None) -> str:
    """``declared`` when given, else the type ``name``'s extension names, else ``application/octet-stream``.

    A compression suffix is an encoding, not the type: ``genome.vcf.gz`` is ``text/x-vcard``.
    """
    if declared:
        return declared
    guessed, _encoding = _table().guess_type(name.lower(), strict=True)
    return guessed or OCTET_STREAM


def is_text_media(media: str | None) -> bool:
    """Whether bytes of ``media`` decode as text: every ``text/*``, and :data:`TEXT_MEDIA_TYPES`."""
    return media is not None and (media.startswith("text/") or media in TEXT_MEDIA_TYPES)


__all__ = [
    "OCTET_STREAM",
    "REGISTERED_TYPES",
    "TEXT_MEDIA_TYPES",
    "AnyFileError",
    "PathEscapeError",
    "UnsafeNameError",
    "is_text_media",
    "looks_binary",
    "media_type",
    "name_collision",
    "resolve_within",
    "safe_name",
]
