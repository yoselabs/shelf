"""Throwaway git repos for the state tests."""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


class Git:
    """A throwaway git repo for state tests: a committer identity, no global config."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.env = {
            "PATH": os.environ["PATH"],
            "HOME": str(root),
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.invalid",
        }

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=self.root, env=self.env, capture_output=True, text=True, check=True).stdout.strip()

    def write(self, rel: str, text: str) -> None:
        (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.root / rel).write_text(text)

    def commit(self, message: str = "c") -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)


@pytest.fixture
def repo(tmp_path: Path) -> Git:
    root = tmp_path / "repo"
    root.mkdir()
    made = Git(root)
    made.git("init", "-q", "-b", "main")
    made.write("app.py", "x = 1\n")
    made.commit("first")
    return made


# What a gate, a hook runner or a git hook leaves in the environment of the suite it runs. `PRE_COMMIT_TO_REF` is the sha being pushed:
# `GateState.green` reads it, so under the pre-push hook every throwaway clone's "this tree already passed" answered no and 13 tests of
# test_inputs.py failed (2026-11-28); `GATE_FAIL_FAST`, `GATE_SLOTS` and the budgets change what `any_gate steps` does the same way.
_OUTER = ("PRE_COMMIT", "GATE_", "ANY_GATE")


@pytest.fixture(autouse=True)
def _private_gate_lease(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A test that runs `steps` queues behind its own lease folder, never the real gate that may be running this suite, and decides
    as if no hook ran it: the outer gate's and hook's variables are dropped (the descriptor number is an xdist worker's pipe in here)."""
    for name in [name for name in os.environ if name.startswith(_OUTER)]:
        monkeypatch.delenv(name)
    monkeypatch.setenv("GATE_LEASE_ROOT", str(tmp_path / "gate-leases"))
