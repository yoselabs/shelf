"""Gate state: the tree a gate passed is remembered, so a push does not run the gate again on exactly that content.

The tree is the content `git add -A` would commit (tracked and untracked files, ignored ones left out) and the upstream merge-base (the
base the changed-file steps diff against). `start` notes the working tree as the gate begins; `passed` records it as green for a gate
only when it is still the tree `start` noted, so a file edited during the run records nothing. `green` says whether HEAD's tree passed,
which is the only case a push may skip the gate: any doubt runs it. A rebase onto a new upstream changes the key, so the gate runs again.

The record is a receipt named `gate-<gate>`, keyed `<tree> <base>`, in the shared receipts file: every worktree of a checkout reads it.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from stream_proc import capture

if TYPE_CHECKING:
    from collections.abc import Mapping

    from any_gate.receipts import Receipts

START = "gate-green.start"
UNJUDGED = "gate-unjudged"  # a step that judged nothing writes why here; `passed` records nothing while it stands
GIT_TIMEOUT = 600.0  # seconds one git call may take: `add -A` on a large tree is the slow one


def _git(repo: Path, env: Mapping[str, str], *args: str) -> str | None:
    """What git prints, stripped; None when git fails (not a repo, no upstream, ...)."""
    try:
        done = capture(["git", *args], cwd=repo, env=env, timeout=GIT_TIMEOUT)
    except OSError:
        return None
    return done.text.strip() if done.exit == 0 else None


def common_dir(repo: Path, env: Mapping[str, str]) -> Path | None:
    """The git directory every worktree of this checkout shares; None outside a repo."""
    found = _git(repo, env, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(found) if found else None


def _own_path(repo: Path, env: Mapping[str, str], name: str) -> Path | None:
    found = _git(repo, env, "rev-parse", "--path-format=absolute", "--git-path", name)
    return Path(found) if found else None


def _base(repo: Path, env: Mapping[str, str]) -> str:
    return _git(repo, env, "merge-base", "HEAD", "@{upstream}") or "none"


def working_key(repo: Path, env: Mapping[str, str]) -> str | None:
    """`<tree> <base>` for the working tree as `git add -A` would commit it; None when git cannot say."""
    index = _own_path(repo, env, "index")
    if index is None:
        return None
    with tempfile.TemporaryDirectory() as scratch:
        temp_index = Path(scratch) / "index"
        if index.is_file():
            # Its stat cache keeps `add -A` from rehashing every file. The copy keeps the index's mtime: git trusts an entry's recorded stat
            # unless the entry is not older than the index file (racily clean); a copy stamped now would hide a same-tick edit.
            shutil.copy2(index, temp_index)
        scratch_env = {**env, "GIT_INDEX_FILE": str(temp_index)}
        if _git(repo, scratch_env, "add", "-A") is None:
            return None
        tree = _git(repo, scratch_env, "write-tree")
    return f"{tree} {_base(repo, env)}" if tree else None


def head_key(repo: Path, env: Mapping[str, str]) -> str | None:
    """`<tree> <base>` for HEAD; None when the working tree is not clean or git cannot say."""
    if _git(repo, env, "status", "--porcelain") != "":
        return None
    tree = _git(repo, env, "rev-parse", "HEAD^{tree}")
    return f"{tree} {_base(repo, env)}" if tree else None


class GateState:
    """The trees `repo`'s gates passed, kept as receipts. `env` is the environment git runs in and `PRE_COMMIT_TO_REF` is read from."""

    def __init__(self, repo: Path, receipts: Receipts, env: Mapping[str, str]) -> None:
        self._repo = repo
        self._receipts = receipts
        self._env = env

    def start(self) -> None:
        """Note the working tree's key as the gate begins; a repo git cannot read notes nothing."""
        marker = _own_path(self._repo, self._env, UNJUDGED)
        if marker is not None:
            marker.unlink(missing_ok=True)
        path, key = _own_path(self._repo, self._env, START), working_key(self._repo, self._env)
        if path is None or key is None:
            return
        try:
            path.write_text(key + "\n")
        except OSError:
            path.unlink(missing_ok=True)

    def unjudged(self, reason: str) -> None:
        """Note that a step of this gate judged nothing (0 suites planned, a check that could not ask): the run records no pass."""
        marker = _own_path(self._repo, self._env, UNJUDGED)
        if marker is None:
            return
        try:
            marker.write_text(reason + "\n")
        except OSError:  # cannot note it: take the safe side and drop the start note, so `passed` records nothing
            start = _own_path(self._repo, self._env, START)
            if start is not None:
                start.unlink(missing_ok=True)

    def unjudged_reason(self) -> str | None:
        """Why this gate's run judged nothing, or None."""
        marker = _own_path(self._repo, self._env, UNJUDGED)
        return marker.read_text().strip() if marker is not None and marker.is_file() else None

    def passed(self, gate: str) -> bool:
        """Record the working tree as green for `gate` when it is the tree `start` noted and no step judged nothing. Never raises."""
        begun = _own_path(self._repo, self._env, START)
        if self.unjudged_reason() is not None:
            if begun is not None:
                begun.unlink(missing_ok=True)
            return False
        if begun is None or not begun.is_file():
            return False
        noted = begun.read_text().strip()
        begun.unlink(missing_ok=True)
        key = working_key(self._repo, self._env)
        if key is None or key != noted:
            return False
        try:
            self._receipts.record(f"gate-{gate}", key)
        except OSError:
            return False
        return True

    def green(self, gate: str) -> bool:
        """Whether HEAD's tree passed `gate` and a push may skip it: a clean tree, HEAD being pushed, and a record."""
        key = head_key(self._repo, self._env)
        if key is None:
            return False
        pushed = self._env.get("PRE_COMMIT_TO_REF", "")
        if pushed and pushed != _git(self._repo, self._env, "rev-parse", "HEAD"):
            return False
        return self._receipts.has(f"gate-{gate}", key)
