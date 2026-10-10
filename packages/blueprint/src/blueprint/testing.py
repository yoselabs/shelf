"""Test doubles for checks: a throwaway git repo and a fake `bd` that answers what a test says.

Stdlib only; used by this package's tests and by anyone writing a new concern's fixtures.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class Repo:
    """A git repo, written to by a test and run through the engine with `env` (fake tools first on PATH)."""

    @classmethod
    def create(cls, root: Path, bin_dir: Path) -> Repo:
        """`git init` at `root`, with a committer identity."""
        root.mkdir()
        bin_dir.mkdir()
        repo = cls(root, bin_dir)
        repo.git("init", "-q", "-b", "main")
        repo.git("config", "user.email", "t@example.invalid")
        repo.git("config", "user.name", "t")
        return repo

    def __init__(self, root: Path, bin_dir: Path) -> None:
        self.root = root
        self.bin_dir = bin_dir
        self.env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}

    def write(self, rel: str, text: str, *, executable: bool = False) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        if executable:
            path.chmod(0o755)
        return path

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, text=True).stdout

    def commit(self) -> None:
        self.git("add", "-A")
        self.git("commit", "-qm", "test", "--no-verify")

    def fake_bd(self, config: dict[str, str], *, lint_exit: int = 0, lint_out: str = "") -> None:
        """A `bd` on PATH: `config show --json` reports `config` from config.yaml; `lint` exits `lint_exit`."""
        shown = json.dumps([{"key": k, "value": v, "source": "config.yaml"} for k, v in config.items()])
        (self.bin_dir / "bd.json").write_text(shown)
        (self.bin_dir / "bd").write_text(
            "#!/bin/sh\n"
            f'if [ "$1" = config ]; then cat "{self.bin_dir}/bd.json"; exit 0; fi\n'
            f'if [ "$1" = lint ]; then echo "{lint_out}"; exit {lint_exit}; fi\n'
            "exit 0\n"
        )
        (self.bin_dir / "bd").chmod(0o755)
