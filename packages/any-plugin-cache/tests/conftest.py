"""A fake claude dir under tmp_path; the real ~/.claude is never touched."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

MARK = "skills/x/x.py"


@pytest.fixture
def claude(tmp_path: Path) -> Path:
    return tmp_path / "claude"


@pytest.fixture
def install(claude: Path) -> Callable[..., Path]:
    def make(version: str, plugin: str = "p", market: str = "m", marker: str | None = MARK) -> Path:
        d = claude / "plugins" / "cache" / market / plugin / version
        d.mkdir(parents=True)
        if marker:
            (d / marker).parent.mkdir(parents=True, exist_ok=True)
            (d / marker).write_text("", encoding="utf-8")
        return d

    return make


@pytest.fixture
def record(claude: Path) -> Callable[[dict[str, object]], None]:
    def write(plugins: dict[str, object]) -> None:
        f = claude / "plugins" / "installed_plugins.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"version": 2, "plugins": plugins}), encoding="utf-8")

    return write
