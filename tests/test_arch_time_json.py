"""Time and stored-JSON hazards as a check (shelf-tyld.10); static, no runtime cost.

- `datetime.utcnow()`, `datetime.utcfromtimestamp()` and a naive `datetime.now()` (no zone argument) are banned: a
  stored moment is aware UTC, written by `any_clock.utc_stamp`. Ruff's DTZ rules (on in the root config) say the same
  per line; this test also covers `tools/` and gives the owner one place to read the rule.
- `time.time()` whose result is subtracted in the same function is flagged: a duration comes from a monotonic clock
  (`any_clock.PhaseClock`, `time.monotonic`). A wall-clock difference against a file mtime or a stored deadline is
  legitimate and sits in `_WALL_CLOCK_DELTA` with its reason (a heuristic: it sees one function, not a stored start).
- `json.dumps(..., default=str)` is banned: it silently turns a datetime or Path into a string, so a stored value changes
  type without a sign. Allowlisted entries say why.

Every allowlist entry says why, and a stale entry (the file no longer hits) fails, so the lists only shrink.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

_NAIVE_NOW = "naive datetime.now()"
_UTC_OLD = "datetime.utcnow / utcfromtimestamp"
_WALL_DELTA = "time.time() subtracted in the same function"
_DEFAULT_STR = "json.dumps(default=str)"

_WALL_CLOCK_DELTA = {
    "timefmt/src/timefmt/__init__.py": "fmt_until: a deadline given as epoch seconds minus now; a wall-clock instant",
    "jsonl-log/src/jsonl_log/_retention.py": "age cutoff against file mtimes, which are wall-clock",
    "blueprint/src/blueprint/concerns/agents.py": "age of a git commit time (wall-clock epoch seconds), shown as hours",
}
_DEFAULT_STR_ALLOWED = {
    "any-frontmatter/src/any_frontmatter/version.py": "stored versions hash YAML dates through default=str; dropping it changes them",
    "mcp-arg-errors/src/mcp_arg_errors/wire.py": "error details rendered as display text on the wire, never stored; best-effort by design",
}
_ALLOWLISTS = {_WALL_DELTA: _WALL_CLOCK_DELTA, _DEFAULT_STR: _DEFAULT_STR_ALLOWED}


def _is_call(node: ast.AST, owner: str, attr: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attr
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == owner
    )


def _reads_wall_clock(tree: ast.AST, tainted: set[str]) -> bool:
    return any(_is_call(n, "time", "time") or (isinstance(n, ast.Name) and n.id in tainted) for n in ast.walk(tree))


def _function_hits_wall_delta(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    tainted: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and _reads_wall_clock(node.value, tainted):
            tainted.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return any(
        isinstance(n, ast.BinOp)
        and isinstance(n.op, ast.Sub)
        and (_reads_wall_clock(n.left, tainted) or _reads_wall_clock(n.right, tainted))
        for n in ast.walk(fn)
    )


def violations_in(source: str) -> set[str]:
    """The rule names a module's source breaks."""
    tree = ast.parse(source)
    found: set[str] = set()
    for node in ast.walk(tree):
        if _is_call(node, "datetime", "utcnow") or _is_call(node, "datetime", "utcfromtimestamp"):
            found.add(_UTC_OLD)
        elif _is_call(node, "datetime", "now") and isinstance(node, ast.Call) and not node.args and not node.keywords:
            found.add(_NAIVE_NOW)
        elif _is_call(node, "json", "dumps") and isinstance(node, ast.Call):
            if any(k.arg == "default" and isinstance(k.value, ast.Name) and k.value.id == "str" for k in node.keywords):
                found.add(_DEFAULT_STR)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and _function_hits_wall_delta(node):
            found.add(_WALL_DELTA)
    return found


def _scan(root: Path) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for path in sorted([*root.glob("packages/*/src/**/*.py"), *root.glob("tools/*.py")]):
        if hits := violations_in(path.read_text(encoding="utf-8")):
            rel = path.relative_to(root)
            out[rel.relative_to("packages").as_posix() if rel.parts[0] == "packages" else rel.as_posix()] = hits
    return out


def _unallowed(found: dict[str, set[str]]) -> dict[str, set[str]]:
    result = {}
    for rel, rules in found.items():
        left = {r for r in rules if rel not in _ALLOWLISTS.get(r, {})}
        if left:
            result[rel] = left
    return result


def test_the_repo_has_no_unlisted_time_or_json_hazard() -> None:
    assert not _unallowed(_scan(_ROOT)), (
        "use any_clock.utc_stamp with an aware datetime, a monotonic clock for a duration, and no default=str; "
        f"or allowlist the file with a reason: {_unallowed(_scan(_ROOT))}"
    )


def test_no_allowlist_entry_is_stale() -> None:
    found = _scan(_ROOT)
    stale = [(rule, rel) for rule, entries in _ALLOWLISTS.items() for rel in entries if rule not in found.get(rel, set())]
    assert not stale, f"the file no longer breaks the rule, delete the entry: {stale}"


def test_every_allowlist_entry_says_why() -> None:
    blank = [rel for entries in _ALLOWLISTS.values() for rel, why in entries.items() if not why.strip()]
    assert not blank, f"each entry needs a reason: {blank}"


def test_a_planted_naive_now_is_flagged(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "x.py").write_text("from datetime import datetime\nstamp = datetime.now()\n")
    assert _scan(tmp_path) == {"tools/x.py": {_NAIVE_NOW}}


def test_a_planted_utcnow_is_flagged(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "x.py").write_text("from datetime import datetime\nstamp = datetime.utcnow()\n")
    assert _scan(tmp_path) == {"tools/x.py": {_UTC_OLD}}


def test_an_aware_now_is_not_flagged(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "x.py").write_text("from datetime import UTC, datetime\nstamp = datetime.now(UTC)\n")
    assert _scan(tmp_path) == {}


def test_a_planted_wall_clock_duration_is_flagged(tmp_path: Path) -> None:
    pkg = tmp_path / "packages" / "demo" / "src" / "demo"
    pkg.mkdir(parents=True)
    (pkg / "m.py").write_text("import time\n\ndef timed(fn):\n    t0 = time.time()\n    fn()\n    return time.time() - t0\n")
    assert _scan(tmp_path) == {"demo/src/demo/m.py": {_WALL_DELTA}}


def test_a_monotonic_duration_is_not_flagged(tmp_path: Path) -> None:
    pkg = tmp_path / "packages" / "demo" / "src" / "demo"
    pkg.mkdir(parents=True)
    (pkg / "m.py").write_text("import time\n\ndef timed(fn):\n    t0 = time.monotonic()\n    fn()\n    return time.monotonic() - t0\n")
    assert _scan(tmp_path) == {}


def test_a_planted_default_str_is_flagged(tmp_path: Path) -> None:
    pkg = tmp_path / "packages" / "demo" / "src" / "demo"
    pkg.mkdir(parents=True)
    (pkg / "m.py").write_text("import json\n\ndef dump(v):\n    return json.dumps(v, default=str)\n")
    assert _scan(tmp_path) == {"demo/src/demo/m.py": {_DEFAULT_STR}}
