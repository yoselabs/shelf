"""Gate state: the tree a gate passed is remembered, so a push does not run the gate again on exactly that content.

The tree is the content `git add -A` would commit (tracked and untracked files, ignored ones left out) and the upstream merge-base (the
base the changed-file steps diff against). `start` notes the working tree as the gate begins; `passed` records it as green for a gate
only when it is still the tree `start` noted, so a file edited during the run records nothing. `green` says whether HEAD's tree passed,
which is the only case a push may skip the gate: any doubt runs it. A rebase onto a new upstream changes the key, so the gate runs again.

The record is a receipt named `gate-<gate>`, keyed `<tree> <base>`, in the shared receipts file: every worktree of a checkout reads it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from any_gate.receipts import Receipts

START = "gate-green.start"


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str | None:
    """What git prints, stripped; None when git fails (not a repo, no upstream, ...)."""
    try:
        done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False, env=env)
    except OSError:
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def common_dir(repo: Path) -> Path | None:
    """The git directory every worktree of this checkout shares; None outside a repo."""
    found = _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(found) if found else None


def _own_path(repo: Path, name: str) -> Path | None:
    found = _git(repo, "rev-parse", "--path-format=absolute", "--git-path", name)
    return Path(found) if found else None


def _base(repo: Path) -> str:
    return _git(repo, "merge-base", "HEAD", "@{upstream}") or "none"


def working_key(repo: Path) -> str | None:
    """`<tree> <base>` for the working tree as `git add -A` would commit it; None when git cannot say."""
    index = _own_path(repo, "index")
    if index is None:
        return None
    with tempfile.TemporaryDirectory() as scratch:
        temp_index = Path(scratch) / "index"
        if index.is_file():
            shutil.copyfile(index, temp_index)  # its stat cache keeps `add -A` from rehashing every file
        env = {**os.environ, "GIT_INDEX_FILE": str(temp_index)}
        if _git(repo, "add", "-A", env=env) is None:
            return None
        tree = _git(repo, "write-tree", env=env)
    return f"{tree} {_base(repo)}" if tree else None


def head_key(repo: Path) -> str | None:
    """`<tree> <base>` for HEAD; None when the working tree is not clean or git cannot say."""
    if _git(repo, "status", "--porcelain") != "":
        return None
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    return f"{tree} {_base(repo)}" if tree else None


class GateState:
    """The trees `repo`'s gates passed, kept as receipts."""

    def __init__(self, repo: Path, receipts: Receipts) -> None:
        self._repo = repo
        self._receipts = receipts

    def start(self) -> None:
        """Note the working tree's key as the gate begins; a repo git cannot read notes nothing."""
        path, key = _own_path(self._repo, START), working_key(self._repo)
        if path is None or key is None:
            return
        try:
            path.write_text(key + "\n")
        except OSError:
            path.unlink(missing_ok=True)

    def passed(self, gate: str) -> bool:
        """Record the working tree as green for `gate` when it is the tree `start` noted. Never raises; True when recorded."""
        begun = _own_path(self._repo, START)
        if begun is None or not begun.is_file():
            return False
        noted = begun.read_text().strip()
        begun.unlink(missing_ok=True)
        key = working_key(self._repo)
        if key is None or key != noted:
            return False
        try:
            self._receipts.record(f"gate-{gate}", key)
        except OSError:
            return False
        return True

    def green(self, gate: str) -> bool:
        """Whether HEAD's tree passed `gate` and a push may skip it: a clean tree, HEAD being pushed, and a record."""
        key = head_key(self._repo)
        if key is None:
            return False
        pushed = os.environ.get("PRE_COMMIT_TO_REF", "")
        if pushed and pushed != _git(self._repo, "rev-parse", "HEAD"):
            return False
        return self._receipts.has(f"gate-{gate}", key)
