"""The `beads` operation: `bd init` + config readback + dolt-push chaining.

Uses the real `bd` binary against real temp git repos — no mocking, same
rationale as `tests/test_hook_installer.py`: the defects this guards against
(config-set not surviving, hooks landing somewhere git doesn't read) are
exactly the kind a mock would paper over.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "tools"))

import onboard.beads as beads_mod  # noqa: E402  -- path-injected, after sys.path setup
from onboard.beads import BeadsOperation  # noqa: E402
from onboard.operations import Outcome, Result, run_all  # noqa: E402

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


_GUARD_APPLIED: dict[str, Result] = {"guard": Result(Outcome.APPLIED, verified=True)}


def test_refuses_when_guard_has_not_run(repo: Path) -> None:
    """Landmine 1: bd init can seize core.hooksPath before an unguarded repo's guard lands."""
    results = run_all([BeadsOperation(repo)])

    assert results["beads"].outcome == Outcome.FAILED
    assert not (repo / ".beads").exists(), "bd init ran despite the unmet guard precondition"


def test_initializes_sets_config_with_readback_and_chains_dolt_push(repo: Path) -> None:
    result = BeadsOperation(repo).run(_GUARD_APPLIED)

    assert result.outcome == Outcome.APPLIED, result.message
    assert result.verified
    assert (repo / ".beads").is_dir()

    hooks = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-path", "hooks"], capture_output=True, text=True, check=True
    ).stdout.strip()
    pre_push = (repo / hooks / "pre-push") if not Path(hooks).is_absolute() else Path(hooks) / "pre-push"
    body = pre_push.read_text()
    assert "bd dolt push" in body
    assert "shelf-onboarding: bd dolt push chain" in body
    end_marker_index = body.index("--- END BEADS INTEGRATION")
    chain_index = body.index("shelf-onboarding: bd dolt push chain")
    assert chain_index > end_marker_index, "dolt-push chain landed inside bd's own managed block"


def test_second_run_is_idempotent(repo: Path) -> None:
    first = BeadsOperation(repo).run(_GUARD_APPLIED)
    second = BeadsOperation(repo).run(_GUARD_APPLIED)

    assert first.outcome == second.outcome == Outcome.APPLIED
    assert second.verified


def test_config_readback_mismatch_is_reported_not_silently_trusted(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulates the exact trap the runbook documents: a `bd config set` that does not survive."""
    real_bd = beads_mod._bd

    def _lying_bd(r: Path, *args: str) -> subprocess.CompletedProcess[str]:
        if args[:2] == ("config", "get"):
            proc = real_bd(r, *args)
            return subprocess.CompletedProcess(proc.args, proc.returncode, stdout="false\n", stderr=proc.stderr)
        return real_bd(r, *args)

    monkeypatch.setattr(beads_mod, "_bd", _lying_bd)

    result = BeadsOperation(repo).run(_GUARD_APPLIED)

    assert result.outcome == Outcome.FAILED
    assert "mismatch" in result.message
