"""One owner for atomic file writes (constitution Article III; bead shelf-tyld.2).

`tempfile.mkstemp` and `os.replace` (the hand-rolled temp-file-then-swap) belong to atomic-io, and to
process-lock and the sqlite packages, which have their own reasons (a lock file, a database set-aside).
Everything else calls atomic-io. `_CURRENT_CALLERS` is the callers that exist today and have not been moved yet;
the consumer wave empties it, and a new entry is a failure to explain, not a place to add a name.
"""

from __future__ import annotations

import ast
from pathlib import Path

_PACKAGES = Path(__file__).resolve().parent.parent / "packages"

_OWNERS = {"atomic-io", "process-lock", "sqlite-store", "sqlite-sidecar"}

# Callers that exist today and are not yet moved onto atomic-io. The consumer wave empties this.
_CURRENT_CALLERS: set[str] = set()


def _offending_calls(source: Path) -> list[str]:
    tree = ast.parse(source.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Attribute) and func.attr == "mkstemp") or (isinstance(func, ast.Name) and func.id == "mkstemp"):
            found.append(f"{source}:{node.lineno} mkstemp")
        elif isinstance(func, ast.Attribute) and func.attr == "replace" and isinstance(func.value, ast.Name) and func.value.id == "os":
            found.append(f"{source}:{node.lineno} os.replace")
    return found


def _callers() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for source in sorted(_PACKAGES.glob("*/src/**/*.py")):
        package = source.relative_to(_PACKAGES).parts[0]
        if package in _OWNERS:
            continue
        hits = _offending_calls(source)
        if hits:
            out.setdefault(package, []).extend(hits)
    return out


def test_only_the_owners_write_through_a_temp_file_and_swap() -> None:
    strangers = {pkg: hits for pkg, hits in _callers().items() if pkg not in _CURRENT_CALLERS}
    assert strangers == {}, "use atomic-io (atomic_write_bytes/text/json) instead of mkstemp or os.replace"


def test_the_allowlist_holds_no_package_that_already_moved() -> None:
    stale = sorted(_CURRENT_CALLERS - set(_callers()))
    assert stale == [], f"drop from _CURRENT_CALLERS, no longer a caller: {stale}"
