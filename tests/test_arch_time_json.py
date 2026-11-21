"""Time and stored-JSON hazards as a check (shelf-tyld.10); static, no runtime cost.

- `datetime.utcnow()`, `datetime.utcfromtimestamp()` and a naive `datetime.now()` (no zone argument) are banned: a
  stored moment is aware UTC, written by `any_clock.utc_stamp`. Ruff's DTZ rules (on in the root config) say the same
  per line; this test also covers `tools/` and gives the owner one place to read the rule.
- `time.time()` whose result is subtracted in the same function is flagged: a duration comes from a monotonic clock
  (`any_clock.PhaseClock`, `time.monotonic`). A wall-clock difference against a file mtime or a stored deadline is
  legitimate and sits in `_WALL_CLOCK_DELTA` with its reason (a heuristic: it sees one function, not a stored start).
- `json.dumps(..., default=str)` is banned: it silently turns a datetime or Path into a string, so a stored value changes
  type without a sign. Allowlisted entries say why.

Every row says why, and a stale row (the file no longer hits) fails, so the lists only shrink.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from any_arch import Row, Rule, check, plant

if TYPE_CHECKING:
    from collections.abc import Iterator

    from any_arch import Hit, Source

_ROOT = Path(__file__).resolve().parent.parent
_SCOPE = ("packages/*/src/**/*.py", "tools/*.py")

_WALL_CLOCK_DELTA = {
    f"packages/{key}": Row(reason)
    for key, reason in {
        "timefmt/src/timefmt/__init__.py": "fmt_until: a deadline given as epoch seconds minus now; a wall-clock instant",
        "jsonl-log/src/jsonl_log/_retention.py": "age cutoff against file mtimes, which are wall-clock",
        "blueprint/src/blueprint/concerns/agents/agents.py": "age of a git commit time (wall-clock epoch seconds), shown as hours",
    }.items()
}
_DEFAULT_STR_ALLOWED = {
    f"packages/{key}": Row(reason)
    for key, reason in {
        "any-frontmatter/src/any_frontmatter/version.py": "stored versions hash YAML dates through default=str; dropping it changes them",
        "mcp-arg-errors/src/mcp_arg_errors/wire.py": (
            "error details rendered as display text on the wire, never stored; best-effort by design"
        ),
    }.items()
}


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


def _utc_old(source: Source) -> Iterator[Hit]:
    for node in ast.walk(source.tree):
        if isinstance(node, ast.Call) and (_is_call(node, "datetime", "utcnow") or _is_call(node, "datetime", "utcfromtimestamp")):
            yield source.rel, node.lineno


def _naive_now(source: Source) -> Iterator[Hit]:
    for node in ast.walk(source.tree):
        if _is_call(node, "datetime", "now") and isinstance(node, ast.Call) and not node.args and not node.keywords:
            yield source.rel, node.lineno


def _default_str(source: Source) -> Iterator[Hit]:
    for node in ast.walk(source.tree):
        if (
            _is_call(node, "json", "dumps")
            and isinstance(node, ast.Call)
            and any(k.arg == "default" and isinstance(k.value, ast.Name) and k.value.id == "str" for k in node.keywords)
        ):
            yield source.rel, node.lineno


def _wall_delta(source: Source) -> Iterator[Hit]:
    for node in ast.walk(source.tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and _function_hits_wall_delta(node):
            yield source.rel, node.lineno


UTC_OLD = Rule("utc-old", "use any_clock.utc_stamp with an aware datetime, not utcnow / utcfromtimestamp", _utc_old, {}, scope=_SCOPE)
NAIVE_NOW = Rule("naive-now", "use any_clock.utc_stamp with an aware datetime, not a naive datetime.now()", _naive_now, {}, scope=_SCOPE)
WALL_DELTA = Rule(
    "wall-clock-duration",
    "use a monotonic clock for a duration, or add a reasoned row",
    _wall_delta,
    _WALL_CLOCK_DELTA,
    scope=_SCOPE,
)
DEFAULT_STR = Rule(
    "json-default-str",
    "no default=str in json.dumps: it silently changes a stored value's type; or add a reasoned row",
    _default_str,
    _DEFAULT_STR_ALLOWED,
    scope=_SCOPE,
)


@pytest.mark.parametrize("rule", [UTC_OLD, NAIVE_NOW, WALL_DELTA, DEFAULT_STR], ids=lambda rule: rule.name)
def test_the_repo_has_no_unlisted_time_or_json_hazard_and_no_row_is_stale(rule: Rule) -> None:
    check(rule, _ROOT)


def test_a_planted_naive_now_is_flagged(tmp_path: Path) -> None:
    assert plant(NAIVE_NOW, tmp_path, "from datetime import datetime\nstamp = datetime.now()\n", "tools/x.py") == {"tools/x.py": [2]}


def test_a_planted_utcnow_is_flagged(tmp_path: Path) -> None:
    assert plant(UTC_OLD, tmp_path, "from datetime import datetime\nstamp = datetime.utcnow()\n", "tools/x.py") == {"tools/x.py": [2]}


def test_an_aware_now_is_not_flagged(tmp_path: Path) -> None:
    assert plant(NAIVE_NOW, tmp_path, "from datetime import UTC, datetime\nstamp = datetime.now(UTC)\n", "tools/x.py") == {}


def test_a_planted_wall_clock_duration_is_flagged(tmp_path: Path) -> None:
    source = "import time\n\ndef timed(fn):\n    t0 = time.time()\n    fn()\n    return time.time() - t0\n"
    assert plant(WALL_DELTA, tmp_path, source) == {"packages/pkg/src/pkg/mod.py": [3]}


def test_a_monotonic_duration_is_not_flagged(tmp_path: Path) -> None:
    source = "import time\n\ndef timed(fn):\n    t0 = time.monotonic()\n    fn()\n    return time.monotonic() - t0\n"
    assert plant(WALL_DELTA, tmp_path, source) == {}


def test_a_planted_default_str_is_flagged(tmp_path: Path) -> None:
    source = "import json\n\ndef dump(v):\n    return json.dumps(v, default=str)\n"
    assert plant(DEFAULT_STR, tmp_path, source) == {"packages/pkg/src/pkg/mod.py": [4]}
