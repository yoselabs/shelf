"""Total reads of untyped frontmatter values — a malformed one is a miss, never an exception.

Frontmatter is user-authored, so any field can hold anything: a mapping where a list
belongs, a date where a string belongs, nothing at all. A reader that walks many files
must turn a value it cannot use into a miss for that one field; an exception takes the
walk, and every other file in it, down.

"Wrote nothing" is ``None``, ``""``, ``[]`` or ``{}`` — the same four lean-wire's
``is_empty`` names, so a reader here and a writer that prunes empty fields agree on what
absent means. ``0`` and ``False`` are present.
"""

from __future__ import annotations

from typing import Any


def written_nothing(value: object) -> bool:
    """Whether the author wrote nothing: ``None``, or an empty ``str``, ``list`` or ``dict``."""
    if value is None:
        return True
    if isinstance(value, (str, list, dict)):
        empty: str | list[Any] | dict[Any, Any] = value
        return len(empty) == 0
    return False


def opt_str(value: object) -> str | None:
    """``value`` as text, or ``None`` when the author wrote nothing. Never raises."""
    if written_nothing(value):
        return None
    try:
        return str(value)
    except Exception:  # noqa: BLE001 — a field whose __str__ explodes is a miss, not a crash
        return None


def str_seq(value: object) -> tuple[str, ...]:
    """A list field as a tuple of non-empty strings. Never raises.

    A non-sequence — a bare string included — reads as empty: a list written as a scalar
    is a mistake to surface elsewhere, not to guess at. Blank items are dropped.
    """
    if not isinstance(value, (list, tuple)):
        return ()
    items: list[Any] | tuple[Any, ...] = value
    return tuple(text for text in (opt_str(item) for item in items) if text is not None)
