#!/usr/bin/env python3
"""Install the shelf's commit guard as a git pre-commit hook in a consumer repo.

Onboarding step 2 — run once per consumer clone (git hooks are per-clone and
cannot be committed, so a fresh clone must install the guard or it is unguarded):

    python /path/to/shelf/tools/hooks/install.py [repo-root]   # default: cwd

Idempotent and marker-guarded: re-running is safe; it refuses to clobber a
foreign pre-commit hook (chain it by hand, or use the pre-commit framework).
"""

from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path

MARKER = "# shelf-guard (no-local-shelf-source)"

HOOK = f"""#!/bin/sh
{MARKER} — managed by the shelf installer; safe to re-run.
SHELF="${{SHELF_HOME:-../shelf}}"
[ -d "$SHELF" ] || SHELF="$HOME/Workspaces/shelf"
GUARD="$SHELF/tools/hooks/forbid-local-shelf-source.py"
[ -f "$GUARD" ] && exec python3 "$GUARD"
exit 0   # guard unavailable (shelf not cloned) -> do not block
"""


def _git_dir(repo: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    git_dir = Path(result.stdout.strip())
    return git_dir if git_dir.is_absolute() else repo / git_dir


def main() -> int:
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    git_dir = _git_dir(repo)
    if git_dir is None:
        print(f"✖ not a git repository: {repo}", file=sys.stderr)
        return 1

    hooks = git_dir / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "pre-commit"

    if hook.exists() and MARKER not in hook.read_text():
        print(f"✖ {hook} already exists and is not shelf-managed — will not clobber.", file=sys.stderr)
        print("  Add this line to it (or use the pre-commit framework):", file=sys.stderr)
        print('    python3 "$SHELF_HOME/tools/hooks/forbid-local-shelf-source.py" || exit 1', file=sys.stderr)
        return 1

    hook.write_text(HOOK)
    hook.chmod(hook.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    print(f"✔ shelf commit guard installed at {hook}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
