"""Shared prompt-shaping helpers."""

from __future__ import annotations

from anyllm.base import PromptParts
from anyllm.providers._prompt import flat_system, flat_user, resolve_system


def test_resolve_system_joins_tuple() -> None:
    assert resolve_system(("a", "b")) == "a\n\nb"
    assert resolve_system(()) == ""
    assert resolve_system("flat") == "flat"


def test_flat_user_flat_path() -> None:
    assert flat_user(None, "hello") == "hello"
    # empty cache_prefix → treated as flat, uses `user`
    assert flat_user(PromptParts(system="s", cache_prefix="", tail="t"), "hello") == "hello"


def test_flat_user_cache_path_concatenates() -> None:
    parts = PromptParts(system="s", cache_prefix="PREFIX", tail="TAIL")
    assert flat_user(parts, "ignored") == "PREFIXTAIL"


def test_flat_system_prefers_parts_on_cache_path() -> None:
    parts = PromptParts(system="from-parts", cache_prefix="PREFIX", tail="TAIL")
    assert flat_system(parts, ("from-arg",)) == "from-parts"


def test_flat_system_uses_arg_on_flat_path() -> None:
    assert flat_system(None, ("from-arg",)) == "from-arg"
    assert flat_system(PromptParts(system="x", cache_prefix="", tail="t"), ("from-arg",)) == "from-arg"
