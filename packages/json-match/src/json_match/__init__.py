"""Read and compare a JSON value the way a test step states it.

- :func:`dig` follows a dotted path: ``items.0.ref``; a number indexes a list (``-1`` the
  last item), ``*`` maps over one. A key that is not there is :data:`MISSING`, apart from a
  key that holds ``null``.
- :func:`compare` checks ``actual {op} expected`` where ``expected`` is the text a step
  quoted: a string compares as is, anything else by its JSON text, a list as its items
  joined by ``", "``.
- :func:`matches` is a subset match: only the keys named are checked.
"""

from __future__ import annotations

import json
import re
from typing import Any, Final

__all__ = ["MISSING", "OPS", "as_text", "compare", "dig", "matches"]


class _Missing:
    def __repr__(self) -> str:
        return "MISSING"


#: A key absent from a value, apart from a key present with ``null``.
MISSING: Final[Any] = _Missing()

#: Every operator :func:`compare` takes, longest first so a regex alternation built from it
#: never stops at a prefix (``is`` inside ``is not``).
OPS: Final = ("does not contain", "is more than", "starts with", "ends with", "contains", "is not", "is")

_INDEX = re.compile(r"-?\d+")


def dig(value: Any, path: str) -> Any:
    """The value at a dotted ``path``: a number indexes a list (``-1`` the last), ``*`` maps over one."""
    if not path or value is MISSING:
        return value
    head, _, rest = path.partition(".")
    if head == "*":
        if not isinstance(value, list):
            msg = f"* on a {type(value).__name__}: {value!r}"
            raise TypeError(msg)
        return [dig(item, rest) for item in value]
    return dig(_step(value, head), rest)


def _step(value: Any, key: str) -> Any:
    if isinstance(value, list) and _INDEX.fullmatch(key):
        index = int(key)
        return value[index] if -len(value) <= index < len(value) else MISSING
    if isinstance(value, dict):
        return value.get(key, MISSING)
    return MISSING


def as_text(value: Any) -> str:
    """A string as is, a list as its items' text joined by ``", "``, anything else as JSON."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ", ".join(as_text(item) for item in value)
    return json.dumps(value)


def compare(actual: Any, op: str, expected: str) -> bool:
    """``actual {op} expected``, for every operator in :data:`OPS`.

    ``contains`` on a list means some item contains the text; ``is more than`` compares numbers.
    """
    if op in {"contains", "does not contain"}:
        found = any(expected in as_text(item) for item in actual) if isinstance(actual, list) else expected in as_text(actual)
        return found == (op == "contains")
    text = as_text(actual)
    if op == "is":
        return text == expected
    if op == "is not":
        return text != expected
    if op == "starts with":
        return text.startswith(expected)
    if op == "ends with":
        return text.endswith(expected)
    if op == "is more than":
        return float(text) > float(expected)
    msg = f"unknown operator {op!r}; expected one of {OPS}"
    raise ValueError(msg)


def matches(expected: Any, actual: Any) -> bool:
    """Subset match: named keys only, objects recursively, a list of objects item by item
    against any actual item, a list of plain values as the same values in any order."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and matches(v, actual[k]) for k, v in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        if all(isinstance(item, dict) for item in expected):
            return all(any(matches(e, a) for a in actual) for e in expected)
        return sorted(map(json.dumps, expected)) == sorted(map(json.dumps, actual))
    return bool(expected == actual)
