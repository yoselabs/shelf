"""One owner for atomic file writes (constitution Article III; bead shelf-tyld.2).

`tempfile.mkstemp` and `os.replace` (the hand-rolled temp-file-then-swap) belong to atomic-io, and to
process-lock and the sqlite packages, which have their own reasons (a lock file, a database set-aside).
Everything else calls atomic-io. The rule's rows would be the packages that call them today and have not been moved yet
(none now); a new row is a failure to explain, not a place to add a name.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

from any_arch import Rule, check, plant

if TYPE_CHECKING:
    from collections.abc import Iterator

    from any_arch import Hit, Source

_ROOT = Path(__file__).resolve().parent.parent
_OWNERS = {"atomic-io", "process-lock", "sqlite-store", "sqlite-sidecar"}


def _swaps(source: Source) -> Iterator[Hit]:
    """Each `mkstemp(...)` and `os.replace(...)` call, keyed by its package; the owner packages are skipped."""
    if source.package in _OWNERS:
        return
    for node in ast.walk(source.tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        mkstemp = (isinstance(func, ast.Attribute) and func.attr == "mkstemp") or (isinstance(func, ast.Name) and func.id == "mkstemp")
        replace = isinstance(func, ast.Attribute) and func.attr == "replace" and isinstance(func.value, ast.Name) and func.value.id == "os"
        if mkstemp or replace:
            yield source.package, node.lineno


ATOMIC_WRITES = Rule(
    "atomic-writes",
    "use atomic-io (atomic_write_bytes/text/json) instead of mkstemp or os.replace",
    _swaps,
    {},
)


def test_only_the_owners_write_through_a_temp_file_and_swap() -> None:
    check(ATOMIC_WRITES, _ROOT)


def test_a_planted_mkstemp_and_os_replace_are_found_and_an_owner_is_not_scanned(tmp_path: Path) -> None:
    source = "import os, tempfile\ntempfile.mkstemp()\nos.replace('a', 'b')\nother.replace('a', 'b')\n"
    assert plant(ATOMIC_WRITES, tmp_path / "a", source) == {"pkg": [2, 3]}
    assert plant(ATOMIC_WRITES, tmp_path / "b", source, "packages/atomic-io/src/atomic_io/mod.py") == {}
