from __future__ import annotations

from pathlib import Path

import pytest
from app_dirs import cache_dir, config_dir, plugin_data_dir, state_dir

_HOME = Path("/home/me")


def test_empty_variable_falls_back() -> None:
    assert config_dir("a", env={"XDG_CONFIG_HOME": ""}, home=_HOME) == _HOME / ".config" / "a"


def test_defaults_read_the_process_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", "/s")
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", "/p")
    assert state_dir("a") == Path("/s/a")
    assert plugin_data_dir() == Path("/p")


@pytest.mark.parametrize("value", [None, "", "relative/dir"])
def test_plugin_data_must_be_set_and_absolute(value: str | None) -> None:
    env = {} if value is None else {"CLAUDE_PLUGIN_DATA": value}
    assert plugin_data_dir(env) is None
    assert cache_dir("a", env=env, home=_HOME, plugin_data=True) == _HOME / ".cache" / "a"


def test_plugin_data_splits_by_kind() -> None:
    env = {"CLAUDE_PLUGIN_DATA": "/p"}
    assert [f("a", env=env, home=_HOME, plugin_data=True) for f in (config_dir, state_dir, cache_dir)] == [
        Path("/p/config"),
        Path("/p/state"),
        Path("/p/cache"),
    ]


@pytest.mark.parametrize("app", ["", ".", "..", "a/b", "a\0b"])
def test_app_must_be_one_folder_name(app: str) -> None:
    with pytest.raises(ValueError, match="single folder name"):
        config_dir(app, env={}, home=_HOME)
