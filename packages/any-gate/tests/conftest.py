"""A throwaway pytest project to run stages and the command against."""

from __future__ import annotations

import os
import subprocess
import textwrap
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.fixture
def project(tmp_path: Path) -> Callable[..., Path]:
    """`project(a="def test_a(): ...", ...)`: `serial` and `quarantine` markers declared, one `test_<name>.py` per keyword."""

    def make(**tests: str) -> Path:
        (tmp_path / "pytest.ini").write_text("[pytest]\nmarkers =\n    serial: runs alone\n    quarantine: flaky, cannot block\n")
        for name, body in tests.items():
            (tmp_path / f"test_{name}.py").write_text(textwrap.dedent(body))
        return tmp_path

    return make


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
