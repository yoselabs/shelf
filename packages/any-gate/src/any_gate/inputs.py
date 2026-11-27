"""Which gate steps a change can affect: each step declares the files it reads, a step whose inputs did not change does no work.

The declaration is `gate-inputs.toml` at the repo root, plain text, one key per step (the recipe's name) and a list of globs
(fnmatch on the whole path, `*` crosses `/`, as in `any_gate.changed`):

    lint = ["*.py", "pyproject.toml"]
    test = ["*"]

A step with no entry always runs (it declared nothing, so it may read anything). Everything runs when the changed files cannot be told
(no base, git failed), when `gate-inputs.toml` itself or the gate's own files changed (`justfile`, `.blueprint/*`), or when asked for
everything (`check-all`). A step skipped here is never started: no process, no file read beyond `gate-inputs.toml` and git's answer.
"""

from __future__ import annotations

import fnmatch
import tomllib
from typing import TYPE_CHECKING

from any_gate import changed

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

FILE = "gate-inputs.toml"
# The gate's own definition: a change to it can change what any step does, so every step runs.
_DEFINITION = (FILE, "justfile", "Justfile", ".blueprint/*")


def declared(repo: Path) -> dict[str, list[str]]:
    """Step name -> globs, from `gate-inputs.toml`; empty when there is no file."""
    path = repo / FILE
    if not path.is_file():
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return {name: [str(g) for g in globs] for name, globs in data.items() if isinstance(globs, list)}


def unaffected(repo: Path, names: Sequence[str], recorded: Callable[[], bool] = lambda: False) -> dict[str, str]:
    """The steps among `names` that declare inputs none of which changed, each with the reason to print.

    An empty change set skips them only when `recorded()` says a gate already passed this tree: a clean tree no gate judged (a fresh
    clone, a merge, a reset) has nothing "changed" and so would judge nothing.
    """
    wanted = declared(repo)
    if not any(name in wanted for name in names):
        return {}  # nothing declared: ask git nothing
    moved = changed.changed(repo)
    if moved is None or any(fnmatch.filter(moved, d) for d in _DEFINITION) or (not moved and not recorded()):
        return {}
    return {
        name: f"{changed.SKIPPED_PREFIX}{name}: none of its declared inputs changed"
        for name in names
        if name in wanted and not any(fnmatch.filter(moved, glob) for glob in wanted[name])
    }
