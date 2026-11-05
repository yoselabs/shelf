"""The root conftest keeps a task-loop run's injected git config out of the tests' own repos."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Runs the root conftest the way pytest imports it, then asks git in a fresh repo what hooks path it sees.
_PROBE = """
import os, runpy, subprocess, sys
runpy.run_path("conftest.py")
assert "GIT_CONFIG_COUNT" not in os.environ, "numbered git config survived"
subprocess.run(["git", "init", "-q", sys.argv[1]], check=True)
got = subprocess.run(["git", "-C", sys.argv[1], "config", "core.hooksPath"], capture_output=True, text=True)
assert got.stdout == "", got.stdout
"""


def test_injected_hooks_path_does_not_reach_a_test(tmp_path: Path) -> None:
    env = {**os.environ, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": "/nonexistent"}
    ran = subprocess.run(
        [sys.executable, "-I", "-c", _PROBE, str(tmp_path / "repo")], cwd=ROOT, env=env, capture_output=True, text=True, check=False
    )
    assert ran.returncode == 0, ran.stdout + ran.stderr
