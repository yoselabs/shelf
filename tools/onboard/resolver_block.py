"""The `resolver-block` operation — projects the shelf resolver block into a consumer's `AGENTS.md` (D5).

Today `docs/consuming-the-shelf.md` §3 says "paste this block" — a pasted block
drifts silently the moment the source changes, with no way to detect it, which
is the constitution's "files are truth; indexes are derived" violated for a doc
fragment. `BLOCK_TEXT` below is the one source; this operation re-projects it
into the same marker-delimited region every run, so a consumer can be checked
for drift the same way `make catalog` checks the ontology indexes.

Marker-delimited, never a full-file rewrite: only the text between
`_BEGIN`/`_END` is ever touched, and a fresh block is always appended at the
true end of the file — never inside, before, or overlapping any other tool's
managed region (this repo's own `AGENTS.md` already carries two from `bd`).

Written in place (`read_text`/`write_text` on the resolved path), never via a
temp-file-plus-rename: an atomic-rename write would unlink a symlinked
`CLAUDE.md -> AGENTS.md` and replace it with a plain file, destroying the
symlink `bd` (and this repo) depends on. Writing in place follows the symlink
and edits its target instead, which is what "without clobbering it" means here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .operations import Outcome, Result

if TYPE_CHECKING:
    from pathlib import Path

_BEGIN = "<!-- BEGIN SHELF RESOLVER BLOCK — managed by shelf's onboarding; safe to re-run -->"
_END = "<!-- END SHELF RESOLVER BLOCK -->"

BLOCK_TEXT = """\
### The shelf — shared micro-software you consume

This project consumes **the shelf** (`github.com/yoselabs/shelf`) — shared, ownable,
contract-guaranteed software pieces, pinned in `pyproject.toml` by git tag. Reach for it before
hand-rolling substrate; adopt only if **DEEP · STABLE · WINS**; contribute back by *promotion*.

**Full behaviour = the shelf loop.** Resolve it **once per session, lazily** — the first time you
consider adopting or promoting substrate, never at startup:

1. Find the local clone: `$SHELF_HOME` → `../shelf` → `~/Workspaces/shelf`.
2. If absent (greenfield), clone it once: `git clone https://github.com/yoselabs/shelf ~/Workspaces/shelf`.
3. Read `<shelf>/docs/agent-loop.md` and follow it. Load once; cache for the session.

Never hit GitHub to start a session or to write code — only to clone (once) or during an actual
adopt/promote (a lazy `git pull` at that checkpoint). Never commit a local `path=`/editable shelf
source (the commit guard blocks it)."""


def _block(text: str) -> str:
    return f"{_BEGIN}\n{text}\n{_END}\n"


def _target(repo: Path) -> Path:
    """`AGENTS.md` if it exists; else `CLAUDE.md` if that's what the repo has; else create `AGENTS.md`."""
    agents = repo / "AGENTS.md"
    if agents.exists():
        return agents
    claude = repo / "CLAUDE.md"
    if claude.exists():
        return claude
    return agents


def _project(current: str, block_text: str) -> str:
    block = _block(block_text)
    start = current.find(_BEGIN)
    end = current.find(_END)
    if start != -1 and end != -1:
        return current[:start] + block + current[end + len(_END) :].lstrip("\n")
    if current and not current.endswith("\n\n"):
        current = current.rstrip("\n") + "\n\n"
    return current + block


@dataclass
class ResolverBlockOperation:
    """Projects `BLOCK_TEXT` into `repo`'s `AGENTS.md`/`CLAUDE.md`."""

    repo: Path
    name: str = "resolver-block"
    requires: tuple[str, ...] = ()

    def run(self, _results: dict[str, Result]) -> Result:
        """Project `BLOCK_TEXT` into the target file, or confirm it is already current."""
        target = _target(self.repo)
        current = target.read_text() if target.exists() else ""
        projected = _project(current, BLOCK_TEXT)
        if projected == current:
            return Result(Outcome.APPLIED, verified=True, message=f"{target} already current")
        target.write_text(projected)
        if target.read_text() != projected:
            return Result(Outcome.FAILED, verified=False, message=f"wrote {target} but the write did not stick")
        return Result(Outcome.APPLIED, verified=True, message=f"projected resolver block into {target}")
