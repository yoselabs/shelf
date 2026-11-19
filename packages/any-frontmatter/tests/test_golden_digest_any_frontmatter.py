"""version_of keeps returning the full sha256 hex of the canonical text: stored versions must not change."""

from __future__ import annotations

import hashlib

from any_frontmatter import Document, canonicalize, version_of


def test_version_of_equals_sha256_of_the_canonical_text() -> None:
    fm = {"title": "Zażółć", "b": [1, 2], "a": {"z": 1}}
    body = "line one\r\nline two ünï\n"
    old = hashlib.sha256(
        canonicalize(Document(frontmatter=fm, body=body)).encode("utf-8"),
    ).hexdigest()
    assert version_of(fm, body) == old
    assert len(old) == 64
