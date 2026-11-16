"""Merge two edits of one YAML document against their common ancestor, keeping ``ours``' comments.

Git merges YAML line by line, so two branches that each add an entry to the end of
one list, or touch neighbouring keys, conflict although they changed different
things. This merges by structure instead: mappings key by key, lists of entries by
the identity ``merge_into`` pairs them with, and a conflict only where both sides
changed one value differently. The result is carried into ``ours``' document, so
what its author wrote around the values stays.
"""

from __future__ import annotations

from collections.abc import Hashable
from typing import TYPE_CHECKING, Any, cast

from yaml_merge.two_way import IDENTITY_KEYS, merge_into

if TYPE_CHECKING:
    from collections.abc import Mapping


class _Absent:
    """A key one side does not have: distinct from a key whose value is ``None``."""


_ABSENT = _Absent()


class MergeConflictError(ValueError):
    """Both sides changed the value at ``path`` differently, so neither can be taken.

    ``path`` runs from the document root: mapping keys, and for a list entry the value
    of its identity key. The empty path is the document itself.
    """

    def __init__(self, path: tuple[Hashable, ...]) -> None:
        self.path = path
        super().__init__(f"both sides changed /{'/'.join(map(str, path))} differently")


def merge3(base: object, ours: object, theirs: object) -> object:
    """``theirs``' changes since ``base``, applied to ``ours``. Raises ``MergeConflictError``.

    Each argument is a parsed document: a ruamel round-trip node, plain data, or
    ``None`` for an absent or empty file. A value one side changed and the other did
    not takes the change; a value both changed the same way takes it once; a value
    both changed differently raises. Mappings merge key by key, ``ours``' key order
    first, then keys only ``theirs`` added. A list merges entry by entry when every
    entry of all three is a mapping carrying the same identity key (first of
    ``name``, ``id``, ``key``) with distinct values; otherwise a list both sides
    changed is a conflict, since position says nothing about which entry is which.

    When ``ours`` is a ``CommentedMap`` or ``CommentedSeq`` the merged values are
    carried into it with ``merge_into`` (mutating it) and it is returned, so its
    comments, blank lines and key order survive; otherwise the result is plain data.
    ``base`` and ``theirs`` are never mutated.
    """
    merged = _merge(_plain(base), _plain(ours), _plain(theirs), ())
    if isinstance(merged, dict):
        return merge_into(ours, cast("dict[str, Any]", merged))
    if isinstance(merged, list):
        return merge_into(ours, cast("list[Any]", merged))
    return merged


def _merge(base: object, ours: object, theirs: object, path: tuple[Hashable, ...]) -> object:
    if theirs in (ours, base):
        return ours
    if base == ours:
        return theirs
    if isinstance(ours, dict) and isinstance(theirs, dict):
        return _merge_maps(_mapping(base), cast("dict[Any, Any]", ours), cast("dict[Any, Any]", theirs), path)
    if isinstance(ours, list) and isinstance(theirs, list):
        keyed = _by_identity(
            [cast("list[Any]", base) if isinstance(base, list) else [], cast("list[Any]", ours), cast("list[Any]", theirs)]
        )
        if keyed is not None:
            return list(_merge_maps(keyed[0], keyed[1], keyed[2], path).values())
    raise MergeConflictError(path)


def _merge_maps(base: Mapping[Any, Any], ours: Mapping[Any, Any], theirs: Mapping[Any, Any], path: tuple[Hashable, ...]) -> dict[Any, Any]:
    merged: dict[Any, Any] = {}
    for key in [*ours, *(key for key in theirs if key not in ours)]:
        value = _merge(base.get(key, _ABSENT), ours.get(key, _ABSENT), theirs.get(key, _ABSENT), (*path, key))
        if value is not _ABSENT:
            merged[key] = value
    return merged


def _by_identity(sides: list[list[Any]]) -> list[dict[Any, Any]] | None:
    """Each list as ``{identity: entry}``, or ``None`` when no candidate key identifies every entry once."""
    entries = [entry for side in sides for entry in side]
    if not all(isinstance(entry, dict) for entry in entries):
        return None
    for key in IDENTITY_KEYS:
        if all(key in entry and isinstance(entry[key], Hashable) for entry in entries):
            keyed = [{entry[key]: entry for entry in side} for side in sides]
            return keyed if all(len(index) == len(side) for index, side in zip(keyed, sides, strict=True)) else None
    return None


def _mapping(value: object) -> dict[Any, Any]:
    return cast("dict[Any, Any]", value) if isinstance(value, dict) else {}


def _plain(value: object) -> object:
    """A fresh copy of ``value`` in plain ``dict``/``list``, so the merge never aliases a node of ``ours``."""
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in cast("dict[Any, Any]", value).items()}
    if isinstance(value, list):
        return [_plain(item) for item in cast("list[Any]", value)]
    return value


__all__ = ["MergeConflictError", "merge3"]
