"""Brace path templates, both ways: a path from placeholders, and placeholders from a path.

Patterns use brace-style placeholders like ``Projects/{id}-{slug}/README.md`` or
``{parent_path}/decisions/{n:04}-{slug}.md``.

- ``resolve(pattern, args)`` builds a forward path from placeholders.
- ``reverse_match(pattern, path)`` extracts placeholders back out, returning ``None``
  when the path does not match.

Placeholders are restricted to ``{name}`` and ``{name:<int-width>}``. A missing argument,
or a non-integer for a width, raises ``PatternError``. What a placeholder may match on the
way back:

- ``{name:N}`` — at least N digits (``resolve`` pads to N and never truncates);
- ``{..._path}`` — a name ending in ``_path`` spans folders (``/``);
- any other ``{name}`` — one path segment, captured lazily.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)(?::(\d+))?\}")


class PatternError(ValueError):
    """An argument the pattern needs is missing, or a width placeholder's value is no integer."""


@dataclass(frozen=True)
class Placeholder:
    name: str
    width: int | None


def parse(pattern: str) -> list[Placeholder]:
    """Extract placeholders from a pattern in declaration order, widths included.

    Public because callers need the WIDTH — `placeholders` drops it.
    """
    found: list[Placeholder] = []
    for match in PLACEHOLDER_RE.finditer(pattern):
        name, width = match.group(1), match.group(2)
        found.append(Placeholder(name=name, width=int(width) if width else None))
    return found


def placeholders(pattern: str) -> list[str]:
    """Return placeholder names in the order they appear (with duplicates)."""
    return [p.name for p in parse(pattern)]


def resolve(pattern: str, args: dict[str, Any]) -> str:
    """Substitute ``args`` into ``pattern``.

    Missing keys raise ``PatternError`` so we never silently drop a placeholder.
    Integer-width placeholders pad with zeros (e.g., ``{n:04}`` → ``0042``).
    """

    def _sub(match: re.Match[str]) -> str:
        name, width = match.group(1), match.group(2)
        if name not in args:
            msg = f"missing placeholder: {name}"
            raise PatternError(msg)
        value = args[name]
        if width:
            try:
                int_value = int(value)
            except (TypeError, ValueError) as exc:
                msg = f"placeholder {name!r} expects integer (width={width}), got {value!r}"
                raise PatternError(msg) from exc
            return format(int_value, f"0{width}d")
        return str(value)

    return PLACEHOLDER_RE.sub(_sub, pattern)


@lru_cache(maxsize=512)
def _to_regex(pattern: str) -> re.Pattern[str]:
    """Compile ``pattern`` to a regex that captures each placeholder.

    Cached: a program's patterns are usually a small fixed set, while ``reverse_match``
    can run once per file per pattern on every walk. Recompiling there was the largest
    avoidable cost in a2kay's vault walk, where this came from.

    Literal segments are escaped; placeholders become named groups.
    Placeholder naming convention:
    - ``{name:N}`` (integer width) → at least N digits: ``resolve`` pads to N and never
      truncates, so id 1000 under ``{id:03}`` is written ``1000`` and must read back.
      Fewer than N does not match, which keeps a loose pattern such as
      ``{parent_path}/{n:04}-{slug}.md`` from claiming every ``12-notes.md`` it sees
    - ``{*_path}`` (name ends in ``_path``) → multi-segment, may span ``/``
    - else → single path segment (no ``/``), captured **lazily**

    Single-segment captures are lazy (``[^/]+?``) so that in an adjacent pair
    like ``{id}-{slug}`` the leading placeholder takes the minimal leading token
    and the trailing one absorbs the rest (``140-agent-bootstrap-and-discovery``
    → id=140, slug=agent-bootstrap-and-discovery), rather than ``id`` greedily
    eating up to the last separator. Matching is ``re.IGNORECASE`` so literal
    segments (e.g. ``README.md``) still match casing variants from files authored
    elsewhere; forward ``resolve`` keeps the canonical casing.
    """
    parts: list[str] = []
    last = 0
    for match in PLACEHOLDER_RE.finditer(pattern):
        parts.append(re.escape(pattern[last : match.start()]))
        name, width = match.group(1), match.group(2)
        if width:
            parts.append(rf"(?P<{name}>\d{{{int(width)},}})")
        elif name.endswith("_path"):
            parts.append(rf"(?P<{name}>.+?)")
        else:
            parts.append(rf"(?P<{name}>[^/]+?)")
        last = match.end()
    parts.append(re.escape(pattern[last:]))
    return re.compile("^" + "".join(parts) + "$", re.IGNORECASE)


def reverse_match(pattern: str, path: str) -> dict[str, str] | None:
    """Extract placeholders from ``path`` for ``pattern``.

    Returns the captured-group dict on match, ``None`` otherwise. Integer-width
    captures are returned as strings; callers coerce as needed.
    """
    compiled = _to_regex(pattern)
    match = compiled.match(path)
    if not match:
        return None
    return match.groupdict()


def pattern_specificity(pattern: str) -> int:
    """Count of literal (non-placeholder) characters in ``pattern``.

    A pattern with more fixed structure constrains a path more tightly, so a path
    that satisfies it is a stronger type signal. Used to break multi-match ties
    deterministically.
    """
    return len(PLACEHOLDER_RE.sub("", pattern))


__all__ = [
    "PLACEHOLDER_RE",
    "PatternError",
    "Placeholder",
    "parse",
    "pattern_specificity",
    "placeholders",
    "resolve",
    "reverse_match",
]
