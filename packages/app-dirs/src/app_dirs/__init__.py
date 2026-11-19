"""app-dirs — where an app keeps its config, state and cache, decided once.

**Stop copying the XDG lookup.** ``config_dir("task-loop")`` is ``$XDG_CONFIG_HOME/task-loop``
or ``~/.config/task-loop``; ``state_dir``, ``cache_dir`` and ``data_dir`` are the same for state
(``~/.local/state``), cache (``~/.cache``) and data (``~/.local/share``). ``tool_home`` finds another tool's dot-folder
(``$CODEX_HOME`` or ``~/.codex``). POSIX only: macOS uses the same XDG layout as
Linux, because the tools this serves already keep their files under ``~/.config`` there.

Per the XDG spec, an unset, empty or *relative* variable is ignored. With ``plugin_data=True``
the folder Claude Code hands a plugin in ``CLAUDE_PLUGIN_DATA`` wins when it is set (and
absolute): ``<it>/config``, ``<it>/state`` and ``<it>/cache``. That variable names whichever
plugin launched the process, so it is opt-in, never read by default.

Nothing is created unless ``create=True``. The environment and home folder can be passed in,
so a caller or a test never needs to patch ``os.environ``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

PLUGIN_DATA_ENV = "CLAUDE_PLUGIN_DATA"

#: kind -> (XDG variable, fallback below the home folder)
_KINDS = {
    "config": ("XDG_CONFIG_HOME", ".config"),
    "state": ("XDG_STATE_HOME", ".local/state"),
    "cache": ("XDG_CACHE_HOME", ".cache"),
    "data": ("XDG_DATA_HOME", ".local/share"),
}


def config_dir(
    app: str, *, plugin_data: bool = False, create: bool = False, env: Mapping[str, str] | None = None, home: Path | None = None
) -> Path:
    """The folder for ``app``'s settings: ``$XDG_CONFIG_HOME/<app>``, else ``~/.config/<app>``."""
    return _resolve("config", app, plugin_data=plugin_data, create=create, env=env, home=home)


def state_dir(
    app: str, *, plugin_data: bool = False, create: bool = False, env: Mapping[str, str] | None = None, home: Path | None = None
) -> Path:
    """The folder for ``app``'s state (logs, history, locks): ``$XDG_STATE_HOME/<app>``, else ``~/.local/state/<app>``."""
    return _resolve("state", app, plugin_data=plugin_data, create=create, env=env, home=home)


def cache_dir(
    app: str, *, plugin_data: bool = False, create: bool = False, env: Mapping[str, str] | None = None, home: Path | None = None
) -> Path:
    """The folder for ``app``'s disposable cache: ``$XDG_CACHE_HOME/<app>``, else ``~/.cache/<app>``."""
    return _resolve("cache", app, plugin_data=plugin_data, create=create, env=env, home=home)


def data_dir(
    app: str, *, plugin_data: bool = False, create: bool = False, env: Mapping[str, str] | None = None, home: Path | None = None
) -> Path:
    """The folder for ``app``'s data (what it keeps, not config): ``$XDG_DATA_HOME/<app>``, else ``~/.local/share/<app>``.

    Also how to find a *foreign* tool's data folder (opencode keeps its logs and ``auth.json`` there).
    """
    return _resolve("data", app, plugin_data=plugin_data, create=create, env=env, home=home)


def tool_home(tool: str, env_var: str | None = None, *, env: Mapping[str, str] | None = None, home: Path | None = None) -> Path:
    """Another tool's own dot-folder: ``$<env_var>`` when it is set and non-empty, else ``~/.<tool>``.

    ``tool_home("codex", "CODEX_HOME")`` is ``$CODEX_HOME`` or ``~/.codex``; ``tool_home("claude")`` is ``~/.claude``
    (no variable consulted). Unlike the XDG lookups the variable is taken as given, relative or not: that is what the
    tool itself does. Never created.
    """
    _check_app(tool, "tool")
    values = os.environ if env is None else env
    named = values.get(env_var) if env_var else None
    return Path(named) if named else (Path.home() if home is None else home) / f".{tool}"


def plugin_data_dir(env: Mapping[str, str] | None = None) -> Path | None:
    """The folder named by ``CLAUDE_PLUGIN_DATA``; ``None`` when it is unset, empty or not absolute."""
    return _absolute((os.environ if env is None else env).get(PLUGIN_DATA_ENV))


def _resolve(kind: str, app: str, *, plugin_data: bool, create: bool, env: Mapping[str, str] | None, home: Path | None) -> Path:
    _check_app(app)
    values = os.environ if env is None else env
    plugin = plugin_data_dir(values) if plugin_data else None
    if plugin is not None:
        path = plugin / kind
    else:
        variable, fallback = _KINDS[kind]
        base = _absolute(values.get(variable)) or (Path.home() if home is None else home) / fallback
        path = base / app
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def _absolute(value: str | None) -> Path | None:
    """``value`` as a path when it is absolute, else ``None`` (the XDG spec: relative values are invalid)."""
    if value and Path(value).is_absolute():
        return Path(value)
    return None


def _check_app(app: str, what: str = "app") -> None:
    if not app or app in {".", ".."} or "/" in app or "\0" in app:
        msg = f"{what} must be a single folder name, got {app!r}"
        raise ValueError(msg)


__all__ = ["PLUGIN_DATA_ENV", "cache_dir", "config_dir", "data_dir", "plugin_data_dir", "state_dir", "tool_home"]
