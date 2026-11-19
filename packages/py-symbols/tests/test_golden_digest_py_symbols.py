"""symbol_hash keeps returning the sha256 hex prefix of the span text: stored evidence hashes must not change."""

from __future__ import annotations

import hashlib

from py_symbols import find, symbol_hash

CODE = 'def f():\n    return "zażółć ☃"\n'


def test_symbol_hash_is_the_sha256_prefix_of_the_span_text() -> None:
    span = find(CODE, "f")
    assert span is not None
    full = hashlib.sha256(span.text.encode()).hexdigest()
    assert symbol_hash(CODE, "f") == full[:12]
    assert symbol_hash(CODE, "f", length=64) == full
    assert symbol_hash(CODE, "f", length=7) == full[:7]
    assert symbol_hash(CODE, "nope") is None
