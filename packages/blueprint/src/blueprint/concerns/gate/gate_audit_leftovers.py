"""Gate audit leftovers: the audit writes nothing tracked, so a tracked baseline or report is stale (ADR 0018)."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

from blueprint.model import Context, Finding, FixedBy, failing, passing

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_DIR = "docs/blueprint"
BASELINE = f"{_DIR}/checkpoints.txt"


def audit_leftovers(ctx: Context) -> Finding:
    """`git ls-files docs/blueprint` lists no `checkpoints.txt` and no Markdown report (a file whose first line is `# Blueprint`)."""
    listed = ctx.git("ls-files", "-z", "--", _DIR)
    if listed is None:
        return ctx.not_a_repository()
    tracked = [p for p in listed.split("\0") if p]
    stale = _leftovers(tracked, lambda p: _is_report(ctx, p))
    if not stale:
        return passing(f"{_DIR} holds no tracked baseline or audit report")
    return failing(
        f"tracked audit leftovers (the audit writes nothing tracked any more): {', '.join(stale)}",
        "run `blueprint gate clean-reports` (git rm of exactly these files); `check --write` reports go to the ignored .blueprint/reports/",
        FixedBy.AUTO,
    )


def _leftovers(tracked: list[str], is_report: Callable[[str], bool]) -> list[str]:
    return [p for p in tracked if p == BASELINE or (p.count("/") == _DIR.count("/") + 1 and p.endswith(".md") and is_report(p))]


def clean(repo: Path) -> int:
    """`blueprint gate clean-reports`: `git rm` the tracked leftovers, print each; 0 when done or nothing to do."""
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", _DIR],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if listed.returncode != 0:
        sys.stderr.write("clean-reports: not a git repository\n")
        return 1

    def report(rel: str) -> bool:
        try:
            return (repo / rel).read_text(encoding="utf-8").startswith("# Blueprint")
        except (OSError, UnicodeDecodeError):
            return False

    stale = _leftovers([p for p in listed.stdout.split("\0") if p], report)
    if not stale:
        sys.stdout.write(f"clean-reports: nothing to remove in {_DIR}\n")
        return 0
    done = subprocess.run(["git", "rm", "-q", "--", *stale], cwd=repo, capture_output=True, text=True, check=False, timeout=60)
    if done.returncode != 0:
        sys.stderr.write(f"clean-reports: git rm failed: {done.stderr.strip()}\n")
        return 1
    sys.stdout.write("".join(f"git rm {p}\n" for p in stale) + "clean-reports: staged; commit them\n")
    return 0


def _is_report(ctx: Context, rel: str) -> bool:
    return (ctx.read(rel) or "").startswith("# Blueprint")
