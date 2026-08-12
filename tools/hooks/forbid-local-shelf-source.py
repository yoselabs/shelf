#!/usr/bin/env python3
"""Guard: refuse a LOCAL shelf source, as a commit hook and as a gate.

The shelf is consumed by git+tag so a consumer builds anywhere. A local
``{ path = ... }`` / ``editable = true`` source is legitimate ONLY as an
*uncommitted* co-development override; committing it ties the repo to one
filesystem and breaks CI and every other checkout.

It flags a ``[tool.uv.sources]`` entry that is local (``path`` or
``editable = true``) AND references the shelf (``"shelf"`` in its ``path`` or
``git`` value). Unrelated local sibling-path deps are left alone.

**Two modes, deliberately reading different things.**

``--staged`` (default) reads the index — what *is about to* be committed. This is
the pre-commit hook's question, and it catches the mistake before it lands.

``--committed`` reads ``HEAD`` — what *has* been committed. This is ``make
guard``'s question. It exists because a hook is per-clone and can be silently
disabled by anything that claims ``core.hooksPath``, so the hook is fast
feedback and the gate is the enforcement.

Note what neither mode reads: the **working tree**. An uncommitted local override
is exactly the supported co-development workflow (``docs/consuming-the-shelf.md``
§1), so failing on it would break the thing the docs tell you to do.

Wire it via pre-commit (``.pre-commit-hooks.yaml`` at the shelf root), as a
native git hook, or as ``make guard`` — see ``docs/consuming-the-shelf.md`` §2.

Exit codes: ``0`` clean · ``1`` offenders found · ``2`` could not check (not a
git repository). A check that cannot run is never reported as a pass.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib

SHELF_MARKER = "shelf"
COULD_NOT_CHECK = 2


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False)


def _staged_pyproject() -> str | None:
    """The pyproject.toml content as it would be committed (staged), or None."""
    result = _git("show", ":pyproject.toml")
    return result.stdout if result.returncode == 0 else None


def _committed_pyproject() -> str | None:
    """The pyproject.toml content at HEAD, or None if there is nothing to read.

    None covers two legitimately-clean cases — a repo with no commits yet, and a
    HEAD carrying no pyproject.toml. Neither is an offense: nothing has been
    committed that could poison a checkout.
    """
    if _git("rev-parse", "HEAD").returncode != 0:
        return None
    result = _git("show", "HEAD:pyproject.toml")
    return result.stdout if result.returncode == 0 else None


def _is_local_shelf_source(src: object) -> bool:
    if not isinstance(src, dict):
        return False
    is_local = "path" in src or src.get("editable") is True
    references_shelf = SHELF_MARKER in str(src.get("path", "")) or SHELF_MARKER in str(src.get("git", ""))
    return is_local and references_shelf


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true", help="check the index (default; the hook's question)")
    mode.add_argument("--committed", action="store_true", help="check HEAD (the gate's question)")
    args = parser.parse_args(argv)

    if _git("rev-parse", "--git-dir").returncode != 0:
        print("✖ cannot check for a local shelf source: not a git repository.", file=sys.stderr)
        print("  This is NOT a pass — the guard could not run at all.", file=sys.stderr)
        return COULD_NOT_CHECK

    committed = args.committed
    content = _committed_pyproject() if committed else _staged_pyproject()
    if content is None:
        return 0

    sources = tomllib.loads(content).get("tool", {}).get("uv", {}).get("sources", {})
    offenders = [name for name, src in sources.items() if _is_local_shelf_source(src)]
    if not offenders:
        return 0

    where = "HEAD carries" if committed else "refusing to commit"
    print(f"✖ {where} a LOCAL shelf source (uncommitted co-dev only):", file=sys.stderr)
    for name in offenders:
        print(f"    [tool.uv.sources] {name}  →  path/editable", file=sys.stderr)
    if committed:
        print("  A committed local source ties this repo to one filesystem.", file=sys.stderr)
        print("  Repoint to a git+tag pin and commit the fix.", file=sys.stderr)
    else:
        print("  Revert these to a git+tag pin before committing.", file=sys.stderr)
    print("  See the shelf's docs/consuming-the-shelf.md. (This guard is not overridable by design.)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
