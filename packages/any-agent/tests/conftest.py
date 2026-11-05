"""Every test runs with a HOME of its own: the harnesses read and write under ~/.claude, ~/.codex and ~/.local/share/opencode."""

import pytest


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for k in ("CODEX_HOME", "XDG_DATA_HOME"):
        monkeypatch.delenv(k, raising=False)
