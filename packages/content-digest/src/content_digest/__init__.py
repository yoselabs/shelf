"""content-digest: one canonical hash for a JSON value or a text.

``digest(value)`` hashes the value's canonical JSON (sorted keys, compact separators, UTF-8, non-ASCII kept):
the same data gives the same digest whatever the key order. A value JSON cannot say (a datetime, a set, bytes, NaN,
a non-string key) is refused with ``TypeError`` or ``ValueError``; nothing is coerced through ``str``, so a datetime
and its string never hash alike. ``digest_text(text)`` hashes the UTF-8 bytes. Both are sha256, cut to ``length``
hex characters (default 12, at most 64).
"""

from __future__ import annotations

import hashlib
import json

__all__ = ["digest", "digest_text"]

DEFAULT_LENGTH = 12
_MAX_LENGTH = 64


def digest(value: object, *, length: int = DEFAULT_LENGTH) -> str:
    """The first ``length`` hex characters of sha256 over the canonical JSON of ``value``."""
    _check_length(length)
    _check_keys(value)
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return _hex(text, length)


def digest_text(text: str, *, length: int = DEFAULT_LENGTH) -> str:
    """The first ``length`` hex characters of sha256 over ``text`` as UTF-8."""
    _check_length(length)
    return _hex(text, length)


def _hex(text: str, length: int) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _check_length(length: int) -> None:
    if not 1 <= length <= _MAX_LENGTH:
        message = f"length must be 1..{_MAX_LENGTH}, got {length}"
        raise ValueError(message)


def _check_keys(value: object) -> None:
    """json.dumps turns 1 into "1" and so would hash {1: x} like {"1": x}; refuse every non-string key."""
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                message = f"JSON object key must be str, got {type(key).__name__}"
                raise TypeError(message)
            _check_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _check_keys(item)
