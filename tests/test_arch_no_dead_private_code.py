"""No private code that nothing calls: a `_name` function, method, class or attribute in `packages/*/src` or `tools` with no reader.

A public name of a library is its API and is read from outside; a private one is read only from inside its own package, so vulture sees
every reader and a finding is dead code (a `_done` helper and an `_is_inside_handler_that_translates` function sat unused until 2026-11-26).
Vulture reads names, not dynamic access, so an allowance row names the file, the symbol and why a reader exists that it cannot see. Public
names and the tests are not judged here: the first need a consumer view, the second are registered by decorators (steps, fixtures).
"""

from __future__ import annotations

from pathlib import Path

import vulture

_ROOT = Path(__file__).resolve().parent.parent
_KINDS = {"function", "method", "class", "attribute", "variable", "property"}

# "path:name" -> why it has a reader vulture cannot see
_ALLOWED = {
    "packages/a2effect/src/a2effect/errors.py:_abstract": "kept: read by string key, cls.__dict__.get('_abstract'), not inherited",
    "packages/stream-proc/src/stream_proc/hold.py:_try_wait": "kept: overrides Popen._try_wait, which CPython's own poll and wait call",
}


def _dead_private_names(root: Path = _ROOT) -> dict[str, int]:
    scan = vulture.Vulture()
    scan.scavenge([str(p) for p in (*sorted(root.glob("packages/*/src")), root / "tools")])
    return {
        f"{Path(item.filename).resolve().relative_to(root.resolve()).as_posix()}:{item.name}": item.first_lineno
        for item in scan.get_unused_code(min_confidence=60)
        if item.typ in _KINDS and item.name.startswith("_") and not item.name.startswith("__")
    }


def test_no_private_name_is_dead_beyond_the_rows_that_explain_it() -> None:
    found = _dead_private_names()
    new = sorted(f"{key} (line {line})" for key, line in found.items() if key not in _ALLOWED)
    stale = sorted(key for key in _ALLOWED if key not in found)
    assert not new, "dead private code: delete it, or add a reasoned row for a reader vulture cannot see:\n" + "\n".join(new)
    assert not stale, "an allowed name is no longer reported dead; delete its row:\n" + "\n".join(stale)
    assert all(reason.startswith("kept:") for reason in _ALLOWED.values())


def test_a_planted_dead_private_function_is_found_and_a_used_or_public_one_is_not(tmp_path: Path) -> None:
    module = tmp_path / "packages" / "pkg" / "src" / "pkg" / "mod.py"
    module.parent.mkdir(parents=True)
    (tmp_path / "tools").mkdir()
    module.write_text("def _dead(): ...\ndef _used(): ...\ndef public(): ...\nvalue = _used()\n", encoding="utf-8")
    assert list(_dead_private_names(tmp_path)) == ["packages/pkg/src/pkg/mod.py:_dead"]
