"""The version bump keeps every other byte of the file."""

from __future__ import annotations

import pytest

from any_plugin_cache import NoVersionError, entry_offset, set_json_version

PLUGIN = '{\n  "name": "p",\n  "version" :  "0.1.0",\n\t"keywords": ["a",   "b"]\n}\n'
MARKET = '{"plugins": [{"name": "a", "version": "1.0.0"}, {"name": "b", "version": "2.0.0"}]}'


def test_sets_version_and_keeps_formatting() -> None:
    assert set_json_version(PLUGIN, "0.2.0") == PLUGIN.replace("0.1.0", "0.2.0")


def test_after_picks_the_named_entry() -> None:
    out = set_json_version(MARKET, "9.9.9", after=entry_offset(MARKET, "b") or 0)
    assert out == MARKET.replace("2.0.0", "9.9.9")


def test_entry_offset_none_when_absent() -> None:
    assert entry_offset(MARKET, "zzz") is None


def test_no_version_raises() -> None:
    with pytest.raises(NoVersionError):
        set_json_version('{"name": "p"}', "1.0.0")
    with pytest.raises(NoVersionError):
        set_json_version(MARKET, "1.0.0", after=len(MARKET))
