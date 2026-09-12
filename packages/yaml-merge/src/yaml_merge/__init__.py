"""Write a payload back into the YAML document a human already wrote.

``model_dump`` produces a plain ``dict``. Dumping that over an existing file
replaces the document — which loses every comment, every blank line, and the key
order the author chose. The file stops being theirs the first time the program
touches it.

**The payload is authoritative about values; the existing document is
authoritative about everything else.**

The case this does NOT cover, and does not need to: a reader that never leaves the
``CommentedMap`` in the first place. If you parse, mutate in place, and dump, the
comments never left and there is nothing to merge. This is for the other shape —
where the values round-trip through something that cannot carry a comment (a
pydantic model, a dataclass, a plain dict) and have to be put back.

Extracted from a2kay, which paid for the comment loss twice: once in its
frontmatter reader and once in its ontology store.

What survives a merge: comments (above a key, and trailing on its line), blank
lines, the author's key order, quoting style, and anchors ruamel understands. What
changes: values the model changed, keys it added (appended), keys it no longer has
(removed, with their comments).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ruamel.yaml.comments import CommentedMap, CommentedSeq

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

#: Keys tried, in order, to pair up entries when merging a list of mappings. A
#: list is the one place where "same position" is a bad proxy for "same thing":
#: inserting a field at the top of `fields:` would otherwise shift every comment
#: down one entry. Falls back to position when no candidate key identifies every
#: entry on both sides.
_IDENTITY_KEYS: tuple[str, ...] = ("name", "id", "key")


def merge_into(existing: object, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """``payload``'s values, carried into ``existing``'s document. Never mutates ``payload``.

    ``existing`` is whatever was parsed from the file — a ``CommentedMap`` when the
    file was there, anything else (``None``, a scalar, a list) when it was not or
    was not a mapping. Anything that is not a mapping is discarded and ``payload``
    is returned as-is: there is no document to preserve, so there is nothing to
    merge into.
    """
    if not isinstance(existing, CommentedMap):
        return payload
    _merge_mapping(existing, payload)
    return existing


def _merge_mapping(target: CommentedMap, payload: Mapping[str, Any]) -> None:
    # ruamel ships no type parameters, so every key and entry read out of one of its
    # containers arrives as an implicit `Any`. `_keys`/`_entries` state the shape in
    # one place instead of letting it leak into every call below.
    for key in [k for k in _keys(target) if k not in payload]:
        # A comment explaining a field that no longer exists is worse than no
        # comment: it reads as current. `del` alone does not remove it — ruamel
        # files the comment block ABOVE a key under the PREVIOUS key — so the block
        # has to be cut by hand before the key goes.
        _drop_leading_comment(target, key)
        del target[key]
    for key, value in payload.items():
        if key in target:
            target[key] = _merged_value(target[key], value)
        else:
            target[key] = value


def _drop_leading_comment(target: CommentedMap, key: str) -> None:
    """Remove the comment block written above ``key``, leaving its neighbour's own alone.

    ruamel stores every comment line between key P and key K as P's *post* comment,
    together with P's own end-of-line comment when it has one. They are told apart by
    position, and only by position: a token that starts with a newline had no
    end-of-line comment to begin with, so all of it belongs to K. Otherwise the first
    line is P's and the rest is K's.

    When ``key`` is the document's first, the block is the mapping's own pre-comment
    instead, and there is no neighbour to protect.
    """
    keys = _keys(target)
    index = keys.index(key)
    if index == 0:
        if target.ca.comment:
            target.ca.comment[1] = None
        return
    token: Any = target.ca.items.get(keys[index - 1], [None, None, None, None])[2]
    if token is None:
        return
    own_line, _, _rest = token.value.partition("\n")
    kept = "" if token.value.startswith("\n") else f"{own_line}\n"
    if kept:
        token.value = kept
    else:
        del target.ca.items[keys[index - 1]]


def _merged_value(current: object, incoming: Any) -> Any:
    if isinstance(current, CommentedMap) and isinstance(incoming, dict):
        _merge_mapping(current, incoming)
        return current
    if isinstance(current, CommentedSeq) and isinstance(incoming, list):
        return _merged_list(current, incoming)
    return incoming


def _merged_list(current: CommentedSeq, incoming: Sequence[Any]) -> CommentedSeq:
    """Pair entries by identity where one exists, else by position.

    The result is built in ``incoming``'s order — the model decides what the list
    holds and in what order — but each entry reuses the document node it matched,
    so its comments travel with it rather than staying at the index it used to sit at.
    """
    sources = _sources(current, incoming)
    merged: list[Any] = [
        item if source is None else _merged_value(current[source], item) for item, source in zip(incoming, sources, strict=True)
    ]
    # Slice assignment on a `CommentedSeq` clears `ca.items` wholesale, and those
    # comments are keyed by INDEX — so an entry that moved would lose its comment, or
    # worse, inherit the one belonging to whatever now sits at its old position. Copy
    # the map across by hand, following each entry to where it ended up.
    was: dict[int, Any] = dict(cast("dict[int, Any]", current.ca.items))
    current[:] = merged
    current.ca.items.clear()
    current.ca.items.update({i: was[source] for i, source in enumerate(sources) if source in was})
    return current


def _sources(current: CommentedSeq, incoming: Sequence[Any]) -> list[int | None]:
    """For each incoming entry, the index in ``current`` it continues — or ``None``, a new one."""
    key = _identity_key(current, incoming)
    if key is None:
        return [i if i < len(current) else None for i in range(len(incoming))]
    by_identity: dict[Any, int] = {entry[key]: i for i, entry in enumerate(_entries(current))}
    return [by_identity.get(cast("Mapping[str, Any]", item)[key]) for item in incoming]


def _identity_key(current: CommentedSeq, incoming: Sequence[Any]) -> str | None:
    """The first candidate key present on EVERY entry of both lists, or ``None``.

    "Every entry" is not fussiness: a key that identifies only some entries would
    merge those by identity and the rest by nothing, which is a third behaviour
    neither caller asked for.
    """
    entries: list[Any] = [*_entries(current), *incoming]
    if not entries or not all(isinstance(entry, dict) for entry in entries):
        return None
    return next((key for key in _IDENTITY_KEYS if all(key in entry for entry in entries)), None)


def _keys(mapping: CommentedMap) -> list[str]:
    return cast("list[str]", list(mapping))


def _entries(sequence: CommentedSeq) -> list[Any]:
    return cast("list[Any]", list(sequence))


__all__ = ["merge_into"]
