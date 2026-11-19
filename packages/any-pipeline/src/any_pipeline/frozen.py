"""What may travel between stages: values nobody can edit in place."""

from __future__ import annotations

from enum import Enum
from pathlib import PurePath

_ATOMS = (str, bytes, int, float, complex, bool, type(None), PurePath, Enum, range)


def is_frozen(value: object) -> bool:
    """Atoms, tuples and frozensets of frozen values, and instances of a frozen dataclass (its fields are the type checker's to police)."""
    if isinstance(value, _ATOMS):
        return True
    if isinstance(value, tuple):
        return all(is_frozen(v) for v in value)
    if isinstance(value, frozenset):
        return all(is_frozen(v) for v in value)
    params = getattr(type(value), "__dataclass_params__", None)
    return bool(params and params.frozen)
