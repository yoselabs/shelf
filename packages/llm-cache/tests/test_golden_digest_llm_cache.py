"""hash_text and make_key keep returning the full sha256 hex of the UTF-8 text (stored keys unchanged)."""

from __future__ import annotations

import hashlib

from llm_cache import hash_text, make_key


def test_hash_text_is_plain_sha256_of_utf8() -> None:
    text = "Zażółć gęślą jaźń ☃ \n"
    assert hash_text(text) == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert len(hash_text("")) == 64
    assert hash_text("") == hashlib.sha256(b"").hexdigest()


def test_make_key_joins_full_hashes() -> None:
    assert make_key("a", "é") == f"{hashlib.sha256(b'a').hexdigest()}:{hashlib.sha256('é'.encode()).hexdigest()}"
