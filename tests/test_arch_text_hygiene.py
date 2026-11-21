"""Text hygiene: lossy decoding is marked, and a directory listing feeding output is sorted (bead shelf-tyld.12).

1. `errors="ignore"` silently deletes data. It is banned except the rows in `_IGNORE_OK`, each with its reason.
2. `errors="replace"` writes U+FFFD in place of bad bytes. Fine for text that is only shown, parsed for a yes/no or
   measured; wrong for text that feeds a hash or a stored file. The call carries `# lossy-ok: <class>: <why>`
   (on one of its lines or the line above) and the class says which kind it is: display, parse, detect, measure, input.
3. A listing call (`glob`, `rglob`, `iterdir`, `os.walk`, `os.listdir`, `os.scandir`) not wrapped in `sorted(...)`
   returns the file system's order, which differs between machines. This is a HEURISTIC: it sees only a listing that
   is not inside a `sorted()` call, not where the result ends up. A hit is fixed when its result feeds a stored file,
   a hash or a printed list, and given a row (with the reason it is order-free) when it does not.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

from any_arch import Row, Rule, check, plant

if TYPE_CHECKING:
    from collections.abc import Iterator

    from any_arch import Hit, Source

_ROOT = Path(__file__).resolve().parent.parent
_SCOPE = ("packages/*/src/**/*.py", "packages/*/bench/**/*.py", "tools/**/*.py")

_IGNORE_OK = {
    "packages/anyembed/src/anyembed/llamacpp.py": Row("drops the half-cut character a token truncation leaves at the end of the bytes"),
}

_LISTING_ATTRS = {"glob", "rglob", "iterdir"}
_OS_LISTING = {"walk", "listdir", "scandir"}
_WRAPPERS = (
    ast.comprehension,
    ast.GeneratorExp,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.Call,
    ast.Tuple,
    ast.List,
    ast.IfExp,
    ast.BoolOp,
    ast.Compare,
    ast.UnaryOp,
    ast.Starred,
    ast.keyword,
    ast.Attribute,
)

# "path::function" -> why the unsorted order cannot reach a stored file, a hash or a printed list.
_UNSORTED_OK = {
    key: Row(reason)
    for key, reason in {
        "packages/any-agent/src/any_agent/supervisor.py::__init__": "a dict of log offsets: looked up by path, never iterated for output",
        "packages/any-json-doc/src/any_json_doc/__init__.py::keys": "the names are sorted on the line that returns them",
        "packages/any-proc/src/any_proc/run.py::user_task_count": "only counted",
        "packages/git-porcelain/src/git_porcelain/real_cache.py::heads_files": "an in-process stat signature; another order is a recompute",
        "packages/stream-proc/src/stream_proc/procfs.py::table": "a dict by pid: callers look up, none rely on its order",
        "packages/blueprint/src/blueprint/gate_test.py::is_workspace": "any() over the glob yields a bool: no order reaches output",
        "packages/blueprint/src/blueprint/model.py::walk": "os.walk runs unwrapped to prune `dirs`; it returns sorted(found)",
        "packages/blueprint/src/blueprint/profile.py::_source_uses": "returns a bool (any file matches): no order reaches output",
        "tools/blueprint_fitness.py::_whole_suite": "builds a set",
        "tools/blueprint_fitness.py::pytest_sessionfinish": "the observed records feed `judge`, which compares sets, and are not stored",
        "packages/any-gate/src/any_gate/changed.py::everything": "sorted on the line that returns the list",
    }.items()
}


def _errors_calls(tree: ast.Module, mode: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and any(kw.arg == "errors" and isinstance(kw.value, ast.Constant) and kw.value.value == mode for kw in node.keywords)
    ]


def _errors_args(tree: ast.Module, mode: str) -> list[ast.Call]:
    """`.decode("utf-8", "replace")` with the mode given positionally is the same lossy call."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"decode", "encode"}
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == mode
    ]


def _errors_ignore(source: Source) -> Iterator[Hit]:
    for call in [*_errors_calls(source.tree, "ignore"), *_errors_args(source.tree, "ignore")]:
        yield source.rel, call.lineno


def _statement_lines(tree: ast.Module, call: ast.Call, lines: list[str]) -> list[str]:
    """The lines of the statement holding `call` (a compound statement: its header only), and the line above."""
    holder: ast.stmt | None = None
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.stmt)
            and node.lineno <= call.lineno <= (node.end_lineno or node.lineno)
            and (holder is None or node.lineno >= holder.lineno)
        ):
            holder = node
    assert holder is not None
    body = getattr(holder, "body", None)
    end = body[0].lineno - 1 if body else holder.end_lineno
    return lines[max(holder.lineno - 2, 0) : end]


def _unmarked_replace(source: Source) -> Iterator[Hit]:
    """`errors="replace"` calls, keyword or positional (`.decode("utf-8", "replace")`), without a `# lossy-ok: ` marker."""
    lines = source.text.splitlines()
    calls = [*_errors_calls(source.tree, "replace"), *_errors_args(source.tree, "replace")]
    for line in sorted(
        {call.lineno for call in calls if not any("# lossy-ok: " in text for text in _statement_lines(source.tree, call, lines))}
    ):
        yield source.rel, line


def _unsorted_listings(source: Source) -> Iterator[Hit]:
    tree = source.tree
    parent = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        func = node.func
        is_path_listing = func.attr in _LISTING_ATTRS
        is_os_listing = func.attr in _OS_LISTING and isinstance(func.value, ast.Name) and func.value.id == "os"
        if not (is_path_listing or is_os_listing):
            continue
        up: ast.AST = node
        sorted_ = False
        while up in parent:
            up = parent[up]
            if isinstance(up, ast.Call) and isinstance(up.func, ast.Name) and up.func.id == "sorted":
                sorted_ = True
                break
            if not isinstance(up, _WRAPPERS):
                break
        if not sorted_:
            scope = node
            while scope in parent and not isinstance(scope, ast.FunctionDef | ast.AsyncFunctionDef):
                scope = parent[scope]
            name = scope.name if isinstance(scope, ast.FunctionDef | ast.AsyncFunctionDef) else "<module>"
            yield f"{source.rel}::{name}", node.lineno


ERRORS_IGNORE = Rule(
    "errors-ignore",
    'errors="ignore" deletes data without a trace: decode strictly or use "replace" with a lossy-ok marker; or add a reasoned row',
    _errors_ignore,
    _IGNORE_OK,
    scope=_SCOPE,
)
ERRORS_REPLACE = Rule(
    "errors-replace",
    "errors=replace needs `# lossy-ok: <display|parse|detect|measure|input>: <why>`; text for a hash or stored file decodes strictly",
    _unmarked_replace,
    {},
    scope=_SCOPE,
)
UNSORTED_LISTING = Rule(
    "unsorted-listing",
    "wrap the listing in sorted(...), or add a row with the reason its order cannot reach output",
    _unsorted_listings,
    _UNSORTED_OK,
    scope=_SCOPE,
)


def test_errors_ignore_is_banned_outside_the_rows() -> None:
    check(ERRORS_IGNORE, _ROOT)


def test_errors_replace_carries_a_lossy_ok_marker() -> None:
    check(ERRORS_REPLACE, _ROOT)


def test_unsorted_listings_are_fixed_or_given_a_row() -> None:
    check(UNSORTED_LISTING, _ROOT)


def test_planted_positional_replace_is_caught_and_a_marker_clears_it(tmp_path: Path) -> None:
    bare = 'def f(raw: bytes) -> str:\n    return raw.decode("utf-8", "replace")\n'
    marked = 'def f(raw: bytes) -> str:\n    # lossy-ok: display: shown to a person\n    return raw.decode("utf-8", "replace")\n'
    assert plant(ERRORS_REPLACE, tmp_path / "a", bare) == {"packages/pkg/src/pkg/mod.py": [2]}
    assert plant(ERRORS_REPLACE, tmp_path / "b", marked) == {}


def test_planted_errors_ignore_is_caught_keyword_and_positional(tmp_path: Path) -> None:
    where = "packages/pkg/src/pkg/mod.py"
    assert plant(ERRORS_IGNORE, tmp_path / "a", 'raw.decode("utf-8", errors="ignore")\n', where) == {where: [1]}
    assert plant(ERRORS_IGNORE, tmp_path / "b", 'raw.decode("utf-8", "ignore")\n', where) == {where: [1]}


def test_planted_unsorted_listing_is_caught_by_function_and_sorted_clears_it(tmp_path: Path) -> None:
    where = "packages/pkg/src/pkg/mod.py"
    assert plant(UNSORTED_LISTING, tmp_path / "a", "def f(p):\n    return list(p.glob('*'))\n", where) == {f"{where}::f": [2]}
    assert plant(UNSORTED_LISTING, tmp_path / "b", "def f(p):\n    return sorted(p.glob('*'))\n", where) == {}
