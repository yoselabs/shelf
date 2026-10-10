"""The `beads` operation: `bd init --skip-hooks`, the strict settings with readback, session settings.

Uses the real `bd` binary against real temp git repos.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "tools"))

import onboard.beads as beads_mod  # noqa: E402  -- path-injected, after sys.path setup
from onboard.beads import BeadsOperation  # noqa: E402
from onboard.operations import Outcome  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("bd") is None, reason="bd is not installed")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "Test")
    (r / "AGENTS.md").write_text("# Project\n")
    _git(r, "add", "AGENTS.md")
    _git(r, "commit", "-qm", "init")
    return r


def test_initializes_without_hooks_and_reads_back_the_strict_set(repo: Path) -> None:
    result = BeadsOperation(repo).run({})
    assert result.outcome == Outcome.APPLIED, result.message
    assert "strict settings read back" in result.message
    hooks_path = subprocess.run(
        ["git", "-C", str(repo), "config", "--local", "core.hooksPath"], capture_output=True, text=True, check=False
    )
    assert hooks_path.stdout.strip() == "", "bd took over core.hooksPath despite --skip-hooks"
    assert not any("BEGIN BEADS" in p.read_text(errors="replace") for p in (repo / ".git" / "hooks").iterdir() if p.is_file())
    for key, value in (("validation.on-create", "error"), ("export.auto", "false"), ("no-git-ops", "true")):
        got = subprocess.run(["bd", "config", "get", key], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
        assert got == value, key


def test_session_settings_are_merged_not_overwritten(repo: Path) -> None:
    settings = repo / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"env": {"KEEP": "1"}, "permissions": {"allow": ["Bash"]}}))
    BeadsOperation(repo).run({})
    data = json.loads(settings.read_text())
    assert data["env"] == {"KEEP": "1", "BD_DISABLE_METRICS": "1"}
    assert data["permissions"] == {"allow": ["Bash"]}
    assert "bd prime" in json.dumps(data["hooks"]["SessionStart"])
    assert "in_progress" in json.dumps(data["hooks"]["Stop"])


def test_second_run_is_idempotent(repo: Path) -> None:
    BeadsOperation(repo).run({})
    first = (repo / ".claude" / "settings.json").read_text()
    again = BeadsOperation(repo).run({})
    assert again.outcome == Outcome.APPLIED, again.message
    assert (repo / ".claude" / "settings.json").read_text() == first


def test_config_readback_mismatch_is_reported_not_silently_trusted(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A `bd config set` that does not survive is a failure, not a pass."""
    real_bd = beads_mod._bd

    def _lying_bd(r: Path, *args: str) -> subprocess.CompletedProcess[str]:
        if args[:2] == ("config", "set"):
            return subprocess.CompletedProcess(args, 0, "", "")
        return real_bd(r, *args)

    monkeypatch.setattr(beads_mod, "_bd", _lying_bd)
    result = BeadsOperation(repo).run({})
    assert result.outcome == Outcome.FAILED
    assert "readback mismatch" in result.message
