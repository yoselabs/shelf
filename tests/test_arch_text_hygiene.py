"""Text hygiene: lossy decoding is marked, and a directory listing feeding output is sorted (bead shelf-tyld.12).

1. `errors="ignore"` silently deletes data. It is banned except the entries in `_IGNORE_OK`, each with its reason.
2. `errors="replace"` writes U+FFFD in place of bad bytes. Fine for text that is only shown, parsed for a yes/no or
   measured; wrong for text that feeds a hash or a stored file. The call carries `# lossy-ok: <class>: <why>`
   (on one of its lines or the line above) and the class says which kind it is: display, parse, detect, measure, input.
3. A listing call (`glob`, `rglob`, `iterdir`, `os.walk`, `os.listdir`, `os.scandir`) not wrapped in `sorted(...)`
   returns the file system's order, which differs between machines. This is a HEURISTIC: it sees only a listing that
   is not inside a `sorted()` call, not where the result ends up. A hit is fixed when its result feeds a stored file,
   a hash or a printed list, and allowlisted (with the reason it is order-free) when it does not.

Blueprint is another owner's package and tools/gate_state.py is the byte-identical copy of its recipe; both are out of
scope here until blueprint adds `encoding=` and the markers itself.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_UNOWNED = ("packages/blueprint/", "tools/gate_state.py")

_IGNORE_OK = {
    "packages/anyembed/src/anyembed/llamacpp.py": "drops the half-cut character a token truncation leaves at the end of the bytes",
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
    "packages/any-agent/src/any_agent/supervisor.py::__init__": "a dict of log offsets: looked up by path, never iterated for output",
    "packages/any-json-doc/src/any_json_doc/__init__.py::keys": "the names are sorted on the line that returns them",
    "packages/any-proc/src/any_proc/run.py::user_task_count": "only counted",
    "packages/git-porcelain/src/git_porcelain/real_cache.py::heads_files": "an in-process stat signature; another order is a recompute",
    "packages/stream-proc/src/stream_proc/procfs.py::table": "a dict by pid: callers look up, none rely on its order",
    "tools/blueprint_fitness.py::_whole_suite": "builds a set",
    "tools/blueprint_fitness.py::pytest_sessionfinish": "the observed records feed `judge`, which compares sets, and are not stored",
    "tools/changed.py::everything": "sorted on the line that returns the list",
}


def _sources() -> dict[str, ast.Module]:
    out: dict[str, ast.Module] = {}
    paths = [*_ROOT.glob("packages/*/src/**/*.py"), *_ROOT.glob("packages/*/bench/**/*.py"), *_ROOT.glob("tools/**/*.py")]
    for path in sorted(paths):
        rel = path.relative_to(_ROOT).as_posix()
        if not rel.startswith(_UNOWNED):
            out[rel] = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
    return out


def _lines(rel: str) -> list[str]:
    return (_ROOT / rel).read_text(encoding="utf-8").splitlines()


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


def test_errors_ignore_is_banned_outside_the_allowlist() -> None:
    hits = {rel for rel, tree in _sources().items() if _errors_calls(tree, "ignore") or _errors_args(tree, "ignore")}
    assert hits - _IGNORE_OK.keys() == set(), (
        'errors="ignore" deletes data without a trace: decode strictly or use "replace" with a lossy-ok marker'
    )
    assert _IGNORE_OK.keys() - hits == set(), "no longer uses errors=ignore: delete its allowlist entry"
    assert all(_IGNORE_OK.values())


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


def test_errors_replace_carries_a_lossy_ok_marker() -> None:
    unmarked: list[str] = []
    for rel, tree in _sources().items():
        lines = _lines(rel)
        # keyword form only: ~27 sites spell it `.decode("utf-8", "replace")` positionally; they are not yet marked
        unmarked += [
            f"{rel}:{call.lineno}"
            for call in _errors_calls(tree, "replace")
            if not any("# lossy-ok: " in line for line in _statement_lines(tree, call, lines))
        ]
    msg = "errors=replace needs `# lossy-ok: <display|parse|detect|measure|input>: <why>`; text for a hash or stored file decodes strictly"
    assert unmarked == [], msg


def _unsorted_listings(tree: ast.Module) -> set[str]:
    parent = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    found: set[str] = set()
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
            found.add(scope.name if isinstance(scope, ast.FunctionDef | ast.AsyncFunctionDef) else "<module>")
    return found


def test_unsorted_listings_are_fixed_or_allowlisted() -> None:
    hits = {f"{rel}::{name}" for rel, tree in _sources().items() for name in _unsorted_listings(tree)}
    assert hits - _UNSORTED_OK.keys() == set(), (
        "wrap the listing in sorted(...), or allowlist it with the reason its order cannot reach output"
    )
    assert _UNSORTED_OK.keys() - hits == set(), "sorted now, or gone: delete its allowlist entry"
    assert all(_UNSORTED_OK.values())
