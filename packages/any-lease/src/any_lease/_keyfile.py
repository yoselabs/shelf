"""A free-form key (``model/UCxxxx``) as one safe, flat file name."""

from __future__ import annotations

import re

from content_digest import digest_text

_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]+")
_READABLE = 48


def keyfile(key: str) -> str:
    """``<readable slug>-<16 hex of sha256(key)>``: flat (no slash), distinct keys never share a name, and a person can still read it.

    The hash alone makes names unique; the slug is only for ``ls``. A key that slugs to nothing (``/``) still gets its hash.
    """
    if not key:
        msg = "key must not be empty"
        raise ValueError(msg)
    slug = _UNSAFE.sub("_", key).strip("._-")[:_READABLE] or "key"
    return f"{slug}-{digest_text(key, length=16)}"
