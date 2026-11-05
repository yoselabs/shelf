"""The root conftest keeps a task-loop run's injected git config out of the tests' own repos."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_injected_hooks_path_does_not_reach_a_test(tmp_path: Path) -> None:
    probe = tmp_path / "test_probe.py"
    probe.write_text(
        "import os, subprocess\n"
        "def test_probe(tmp_path):\n"
        "    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)\n"
        "    got = subprocess.run(['git', '-C', str(tmp_path), 'config', 'core.hooksPath'], capture_output=True, text=True)\n"
        "    assert got.stdout == ''\n"
        "    assert 'GIT_CONFIG_COUNT' not in os.environ\n"
    )
    env = {**os.environ, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": "/nonexistent"}
    ran = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "conftest", "-p", "no:cacheprovider", "-q", str(probe)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ran.returncode == 0, ran.stdout + ran.stderr
