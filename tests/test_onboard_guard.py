"""The `guard` Operation — a thin wrapper around `tools/hooks/install.py`.

Does not re-prove liveness (`tests/test_hook_installer.py` owns that); proves
only that the wrapper reports the three outcomes the underlying CLI's exit
codes mean, per `onboard-consumer-skill` D3.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "tools"))

from onboard.guard import GuardOperation  # noqa: E402  -- path-injected, after sys.path setup
from onboard.operations import Outcome  # noqa: E402  -- path-injected, after sys.path setup


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "Test")
    (r / "pyproject.toml").write_text('[project]\nname = "c"\nversion = "0.1.0"\n')
    _git(r, "add", "pyproject.toml")
    _git(r, "commit", "-qm", "init")
    return r


@pytest.fixture(autouse=True)
def _shelf_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # A dedicated HOME, never the repo's own tree — install.py may write under
    # $HOME (e.g. macOS Library/), which would otherwise look like the operation
    # dirtying the repo.
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SHELF_HOME", str(_ROOT))


def test_installs_and_verifies_reports_applied(repo: Path) -> None:
    result = GuardOperation(repo).run({})

    assert result.outcome == Outcome.APPLIED
    assert result.verified
    assert result.satisfied


def test_could_not_verify_is_reported_as_could_not_apply_not_success(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SHELF_HOME", raising=False)
    monkeypatch.setenv("HOME", str(repo.parent / "nowhere"))
    (repo.parent / "nowhere").mkdir(parents=True, exist_ok=True)

    result = GuardOperation(repo).run({})

    assert result.outcome == Outcome.COULD_NOT_APPLY
    assert not result.satisfied


def test_a_foreign_hook_is_reported_as_failed(repo: Path) -> None:
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "pre-commit").write_text("#!/bin/sh\necho mine\n")

    result = GuardOperation(repo).run({})

    assert result.outcome == Outcome.FAILED
    assert not result.satisfied
