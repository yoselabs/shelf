"""Which gate steps a change can affect: each step declares the files it reads, a step whose inputs did not change does no work.

Two files, one shape: one key per step (the recipe's name) and a list of globs (fnmatch on the whole path, `*` crosses `/`, as in
`any_gate.changed`):

    lint = ["*.py", "pyproject.toml"]
    test = ["*"]

`.blueprint/step-inputs.toml` is the blueprint's DEFAULT for each step it renders (per stack, rendered with the justfile parts). The
repo's `gate-inputs.toml` holds only its exceptions: a list there WIDENS the step's default (the union); a step the blueprint knows
nothing about (a repo's own) declares its inputs there. A repo may NARROW a step only with a reason, `[narrow] step = "why"`: then
its own list replaces the default (the audit fails a `[narrow]` entry with no reason).

A step with no default and no entry always runs (it declared nothing, so it may read anything). Everything runs when the changed
files cannot be told (no base, git failed), when either file or the gate's own files changed (`justfile`, `.blueprint/*`), or when
asked for everything (`check-all`). A step skipped here is never started: no process, no file read beyond the two files and git's
answer.
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
DEFAULTS = ".blueprint/step-inputs.toml"
# The gate's own definition: a change to it can change what any step does, so every step runs.
_DEFINITION = (FILE, DEFAULTS, "justfile", "Justfile", ".blueprint/*")


def _load(path: Path) -> dict[str, object]:
    return tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _lists(data: dict[str, object]) -> dict[str, list[str]]:
    return {name: [str(g) for g in globs] for name, globs in data.items() if isinstance(globs, list)}


def declared(repo: Path) -> dict[str, list[str]]:
    """Step name -> globs: the blueprint's defaults widened by the repo's list; a `[narrow]`ed step takes the repo's list alone."""
    effective = _lists(_load(repo / DEFAULTS))
    own = _load(repo / FILE)
    narrowed = own.get("narrow")
    narrow = set(narrowed) if isinstance(narrowed, dict) else set()
    for name, globs in _lists(own).items():
        base = [] if name in narrow else effective.get(name, [])
        effective[name] = [*base, *(g for g in globs if g not in base)]
    return effective


def _globs(globs: Sequence[str]) -> str:
    """The globs a reason names: the first three, then an ellipsis."""
    return " ".join(globs[:3]) + (" …" if len(globs) > 3 else "")


def explain(repo: Path, names: Sequence[str], recorded: Callable[[], bool] = lambda: False) -> tuple[dict[str, str], dict[str, str]]:
    """`(skips, runs)`: the steps among `names` not to start, each with the `skipped ...` line to print, and the others each with a
    one-line reason they run (`run test: 3 changed (*.py)`).

    A step declaring inputs none of which changed is skipped. An empty change set skips them only when `recorded()` says a gate
    already passed this tree: a clean tree no gate judged (a fresh clone, a merge, a reset) has nothing "changed".
    """
    wanted = declared(repo)
    blind = {name: f"run {name}: declares no inputs" for name in names if name not in wanted}
    if len(blind) == len(names):
        return {}, blind  # nothing declared: ask git nothing
    moved = changed.changed(repo)
    everything = (
        "changed files unknown"
        if moved is None
        else "gate definition changed"
        if any(fnmatch.filter(moved, d) for d in _DEFINITION)
        else "no gate passed this tree"
        if not moved and not recorded()
        else None
    )
    skips: dict[str, str] = {}
    runs = dict(blind)
    for name in names:
        if name in blind:
            continue
        if everything is not None or moved is None:
            runs[name] = f"run {name}: {everything}"
            continue
        hits = [glob for glob in wanted[name] if fnmatch.filter(moved, glob)]
        if hits:
            count = len({path for glob in hits for path in fnmatch.filter(moved, glob)})
            runs[name] = f"run {name}: {count} changed ({_globs(hits)})"
        else:
            skips[name] = f"{changed.SKIPPED_PREFIX}{name}: none of {_globs(wanted[name])} changed"
    return skips, {name: runs[name] for name in names if name in runs}


def unaffected(repo: Path, names: Sequence[str], recorded: Callable[[], bool] = lambda: False) -> dict[str, str]:
    """The steps among `names` that declare inputs none of which changed, each with the reason to print (`explain`'s skips)."""
    return explain(repo, names, recorded)[0]
