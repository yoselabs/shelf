"""The `verify` operation (D3, tasks 2.4-2.5): re-running IS re-verifying.

The landmine-5 test is the point of this file — a `bd config set` that
`git checkout` silently reverts must be CAUGHT by a second `verify` pass, not
reported as still passing because a file happened to exist.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "tools"))

from onboard.beads import BeadsOperation  # noqa: E402  -- path-injected, after sys.path setup
from onboard.operations import Outcome, Result  # noqa: E402
from onboard.verify import all_satisfied, verify  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("bd") is None, reason="bd is not installed")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


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


@dataclass
class _AlwaysOk:
    name: str = "always-ok"
    requires: tuple[str, ...] = ()

    def run(self, results: dict[str, Result]) -> Result:
        return Result(Outcome.APPLIED, verified=True)


@dataclass
class _AlwaysFails:
    name: str = "always-fails"
    requires: tuple[str, ...] = ()

    def run(self, results: dict[str, Result]) -> Result:
        return Result(Outcome.FAILED, verified=False, message="never works")


def test_verify_reports_per_operation_not_a_single_boolean() -> None:
    results = verify([_AlwaysOk(), _AlwaysFails()])

    assert set(results) == {"always-ok", "always-fails"}
    assert results["always-ok"].outcome == Outcome.APPLIED
    assert results["always-fails"].outcome == Outcome.FAILED


def test_all_satisfied_is_true_only_when_every_operation_is() -> None:
    assert all_satisfied(verify([_AlwaysOk()]))
    assert not all_satisfied(verify([_AlwaysOk(), _AlwaysFails()]))


def test_config_revert_is_caught_and_self_healed_by_a_second_verify_pass(repo: Path) -> None:
    """The landmine-5 scenario: `bd config set` succeeds, `.beads/config.yaml` is a
    TRACKED file (committed by `bd init` with the export keys unset), and a plain
    `git checkout -- .beads/config.yaml` silently reverts it with no signal from
    `bd` itself. shelf hit exactly this, 2026-08-12.

    A `verify` that trusted the first run's cached Result would report a stale
    pass. This one doesn't cache anything: it re-runs the operation, which
    re-executes `bd config set` + `bd config get` from scratch (see
    `beads.py`'s module docstring). The revert is therefore not silently
    missed -- it's caught AND fixed in the same pass, which is what "an
    idempotent, effect-asserting operation" buys over a read-only check that
    would only report the drift and leave it for a human to re-run.
    """
    guard_stub = _AlwaysOk(name="guard")
    beads_op = BeadsOperation(repo)

    first = beads_op.run({"guard": Result(Outcome.APPLIED, verified=True)})
    assert first.outcome == Outcome.APPLIED, first.message

    # `bd init`'s own commit ships the config with the export keys unset --
    # reverting to it is exactly the trap: an ordinary tree-rewinding git
    # operation undoing an in-effect `bd config set` with zero warning.
    _git(repo, "checkout", "--", ".beads/config.yaml")
    reverted = subprocess.run(["bd", "config", "get", "export.auto"], cwd=repo, capture_output=True, text=True, check=True)
    assert reverted.stdout.strip() != "true", "test setup didn't actually revert anything -- nothing to catch"

    second = verify([guard_stub, beads_op])["beads"]

    assert second.outcome == Outcome.APPLIED, second.message
    healed = subprocess.run(["bd", "config", "get", "export.auto"], cwd=repo, capture_output=True, text=True, check=True)
    assert healed.stdout.strip() == "true", "verify did not actually re-check -- it trusted the first run's result"
