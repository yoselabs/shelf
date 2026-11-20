from __future__ import annotations

from pathlib import Path

import pytest
from app_dirs import config_dir, data_dir, ensure, plugin_data_dir, plugin_dir, state_dir, tool_home

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
    assert plugin_dir("cache", "a", env=env, home=_HOME) == _HOME / ".cache" / "a"


def test_plugin_data_splits_by_kind() -> None:
    env = {"CLAUDE_PLUGIN_DATA": "/p"}
    assert [plugin_dir(kind, "a", env=env, home=_HOME) for kind in ("config", "state", "cache", "data")] == [
        Path("/p/config"),
        Path("/p/state"),
        Path("/p/cache"),
        Path("/p/data"),
    ]


def test_plugin_dir_refuses_a_bad_app_name_even_when_the_plugin_folder_is_set() -> None:
    with pytest.raises(ValueError, match="single folder name"):
        plugin_dir("config", "a/b", env={"CLAUDE_PLUGIN_DATA": "/p"}, home=_HOME)


def test_ensure_makes_the_folder_and_returns_it(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b"
    assert ensure(target) == target
    assert target.is_dir()
    assert ensure(target) == target


@pytest.mark.parametrize("app", ["", ".", "..", "a/b", "a\0b"])
def test_app_must_be_one_folder_name(app: str) -> None:
    with pytest.raises(ValueError, match="single folder name"):
        config_dir(app, env={}, home=_HOME)


def test_data_dir_follows_xdg_data_home() -> None:
    # What any-agent hand-rolled for opencode: $XDG_DATA_HOME/opencode, else ~/.local/share/opencode.
    assert data_dir("opencode", env={"XDG_DATA_HOME": "/d"}, home=_HOME) == Path("/d/opencode")
    assert data_dir("opencode", env={}, home=_HOME) == _HOME / ".local" / "share" / "opencode"
    assert data_dir("opencode", env={"XDG_DATA_HOME": "rel"}, home=_HOME) == _HOME / ".local" / "share" / "opencode"


def test_tool_home_is_the_tools_variable_else_its_dotfolder() -> None:
    # What any-agent hand-rolled for codex: $CODEX_HOME, else ~/.codex.
    assert tool_home("codex", "CODEX_HOME", env={"CODEX_HOME": "/c"}, home=_HOME) == Path("/c")
    assert tool_home("codex", "CODEX_HOME", env={"CODEX_HOME": ""}, home=_HOME) == _HOME / ".codex"
    assert tool_home("codex", "CODEX_HOME", env={}, home=_HOME) == _HOME / ".codex"


def test_tool_home_without_a_variable_is_the_dotfolder() -> None:
    # claude: ~/.claude, no variable consulted.
    assert tool_home("claude", env={"CLAUDE_HOME": "/x"}, home=_HOME) == _HOME / ".claude"


def test_tool_home_reads_the_process_environment_and_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEX_HOME", "/c")
    assert tool_home("codex", "CODEX_HOME") == Path("/c")
    monkeypatch.delenv("CODEX_HOME")
    assert tool_home("codex", "CODEX_HOME") == Path.home() / ".codex"


@pytest.mark.parametrize("tool", ["", ".", "..", "a/b", "a\0b"])
def test_tool_must_be_one_folder_name(tool: str) -> None:
    with pytest.raises(ValueError, match="single folder name"):
        tool_home(tool, env={}, home=_HOME)
