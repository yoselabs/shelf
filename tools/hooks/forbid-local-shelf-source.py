#!/usr/bin/env python3
"""Pre-commit guard: refuse to commit a LOCAL shelf source.

The shelf is consumed by git+tag so a consumer builds anywhere. A local
``{ path = ... }`` / ``editable = true`` source is legitimate ONLY as an
*uncommitted* co-development override; committing it ties the repo to one
filesystem and breaks CI and every other checkout. This hook makes that
mistake structurally impossible — no parallel agent session can poison a
consumer by forgetting to revert.

It flags a ``[tool.uv.sources]`` entry that is local (``path`` or
``editable = true``) AND references the shelf (``"shelf"`` in its ``path`` or
``git`` value). Unrelated local sibling-path deps are left alone.

Wire it via pre-commit (``.pre-commit-hooks.yaml`` at the shelf root) or as a
native git hook — see ``docs/consuming-the-shelf.md`` §2.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib

SHELF_MARKER = "shelf"


def _staged_pyproject() -> str | None:
    """The pyproject.toml content as it would be committed (staged), or None."""
    result = subprocess.run(
        ["git", "show", ":pyproject.toml"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def _is_local_shelf_source(src: object) -> bool:
    if not isinstance(src, dict):
        return False
    is_local = "path" in src or src.get("editable") is True
    references_shelf = SHELF_MARKER in str(src.get("path", "")) or SHELF_MARKER in str(src.get("git", ""))
    return is_local and references_shelf


def main() -> int:
    content = _staged_pyproject()
    if content is None:
        return 0

    sources = tomllib.loads(content).get("tool", {}).get("uv", {}).get("sources", {})
    offenders = [name for name, src in sources.items() if _is_local_shelf_source(src)]
    if not offenders:
        return 0

    print("✖ refusing to commit a LOCAL shelf source (uncommitted co-dev only):", file=sys.stderr)
    for name in offenders:
        print(f"    [tool.uv.sources] {name}  →  path/editable", file=sys.stderr)
    print("  Revert these to a git+tag pin before committing.", file=sys.stderr)
    print("  See the shelf's docs/consuming-the-shelf.md. (This guard is not overridable by design.)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
