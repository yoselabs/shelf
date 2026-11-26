"""Injection (constitution Article II): no module-level I/O and no global mutable state in `packages/*/src`.

Collaborators arrive as instances passed in at the edge. A hit is

- I/O or an environment read that runs at import time: a call to `open`, a file read or write, a directory probe, a
  subprocess, a socket, a database connect, `shutil.which`, `os.environ`, `os.getenv`, `Path.home()`, and the process hooks
  `atexit.register`, `os.register_at_fork`, `signal.signal`; found in the
  statements of a module or of a class body, never inside a function (a function body runs when called, not at import),
- a `global` statement, anywhere (the function rebinds module state), or
- a module-level `dict`/`list`/`set`/`deque`/`defaultdict`/`Counter`/`OrderedDict`/`WeakSet`/`count` bound to a name that some
  function of the same module mutates in place (`NAME[k] = v`, `NAME.append(...)`, `del NAME[k]`, `NAME += ...`) or hands to a
  function of the same module or to `next` (`_open(path, NAME)`, `next(NAME)`).

Not judged: a module-level instance of a stateful class (`_CACHE = _Cache()`); only the container kinds above are clear cases.

Not hits: constants and frozen data (a literal nothing mutates, a `MappingProxyType`, a tuple, a `frozenset`); a literal
filled by module-level code only (built once at import, then read); `functools.cache` / `lru_cache` (a separate question,
not judged here).

Each file with hits is a row with an exact count. Reason prefixes:

- `outcome:` the module-level state is the documented design of the module (a registry filled by decorators at import)
- `debt:` real module-level I/O or global state still owed a conversion to an injected collaborator
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from any_arch import Row, Rule, check, plant, rows

from tests.arch_keys import DEBT_UNTIL

if TYPE_CHECKING:
    from collections.abc import Iterator

    from any_arch import Hit, Source

_ROOT = Path(__file__).resolve().parent.parent

_IO_CALLS = frozenset(
    {
        "open",
        "os.system",
        "os.popen",
        "os.getenv",
        "os.getcwd",
        "os.listdir",
        "os.scandir",
        "os.walk",
        "os.makedirs",
        "os.mkdir",
        "sqlite3.connect",
        "socket.socket",
        "socket.create_connection",
        "shutil.which",
        "Path.home",
        "Path.cwd",
        "urlopen",
        "platform.node",
        "getpass.getuser",
        "tempfile.gettempdir",
        "atexit.register",
        "os.register_at_fork",
        "signal.signal",
    },
)
_IO_PREFIXES = ("subprocess.", "shutil.", "requests.", "httpx.", "urllib.request.")
_IO_METHODS = frozenset(
    {
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
        "mkdir",
        "exists",
        "is_file",
        "is_dir",
        "iterdir",
        "glob",
        "rglob",
        "unlink",
        "stat",
        "touch",
    },
)
_CONTAINERS = frozenset(
    {
        "dict",
        "list",
        "set",
        "deque",
        "defaultdict",
        "Counter",
        "OrderedDict",
        "WeakSet",
        "WeakValueDictionary",
        "WeakKeyDictionary",
        "count",
        "itertools.count",
    },
)
_MUTATORS = frozenset(
    {
        "append",
        "add",
        "update",
        "pop",
        "popitem",
        "clear",
        "extend",
        "setdefault",
        "remove",
        "discard",
        "insert",
        "appendleft",
        "popleft",
        "sort",
        "reverse",
    },
)


def _import_time(statements: list[ast.stmt]) -> Iterator[ast.AST]:
    """Every node that runs at import: the statements, class bodies included, function bodies and lambdas excluded."""
    stack: list[ast.AST] = list(statements)
    while stack:
        node = stack.pop()
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            continue  # runs when called; its decorators and defaults are registration, not I/O
        yield node
        stack.extend(ast.iter_child_nodes(node))


def _is_io(node: ast.AST) -> bool:
    if isinstance(node, ast.Attribute):
        return ast.unparse(node) == "os.environ"
    if not isinstance(node, ast.Call):
        return False
    name = ast.unparse(node.func)
    if name in _IO_CALLS or name.startswith(_IO_PREFIXES):
        return True
    return isinstance(node.func, ast.Attribute) and node.func.attr in _IO_METHODS


def _is_container(value: ast.expr | None) -> bool:
    if isinstance(value, ast.Dict | ast.List | ast.Set | ast.DictComp | ast.ListComp | ast.SetComp):
        return True
    return isinstance(value, ast.Call) and ast.unparse(value.func) in _CONTAINERS


def _module_containers(tree: ast.Module) -> dict[str, int]:
    """name -> line of each module-level mutable container binding."""
    found: dict[str, int] = {}
    for node in _import_time(tree.body):
        if isinstance(node, ast.Assign) and _is_container(node.value):
            found.update({t.id: node.lineno for t in node.targets if isinstance(t, ast.Name)})
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and _is_container(node.value):
            found[node.target.id] = node.lineno
    return found


def _locals(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    arguments = function.args
    names = {a.arg for a in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs, arguments.vararg, arguments.kwarg] if a}
    names.update(n.id for n in ast.walk(function) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
    return names


def _mutated_in(function: ast.FunctionDef | ast.AsyncFunctionDef, containers: dict[str, int], callees: set[str]) -> set[str]:
    shadowed = _locals(function)
    mutated: set[str] = set()
    for node in ast.walk(function):
        target: ast.expr | None = None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _MUTATORS:
            target = node.func.value
        elif isinstance(node, ast.Call) and ast.unparse(node.func) in callees:  # handed to a callee that may mutate it
            mutated.update(a.id for a in node.args if isinstance(a, ast.Name) and a.id in containers and a.id not in shadowed)
        elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store | ast.Del):
            target = node.value
        elif isinstance(node, ast.AugAssign):
            target = node.target
        if isinstance(target, ast.Name) and target.id in containers and target.id not in shadowed:
            mutated.add(target.id)
    return mutated


def _mutated_attributes(tree: ast.Module) -> set[str]:
    """Attribute names some code outside an `__init__` mutates in place (`x.attr.append(..)`, `x.attr[k] = ..`)."""
    found: set[str] = set()
    building = {id(n) for init in ast.walk(tree) if isinstance(init, ast.FunctionDef) and init.name == "__init__" for n in ast.walk(init)}
    for node in ast.walk(tree):
        if id(node) in building:
            continue
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _MUTATORS:
            target: ast.expr = node.func.value
        elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store | ast.Del):
            target = node.value
        else:
            continue
        if isinstance(target, ast.Attribute):
            found.add(target.attr)
    return found


def _stateful_classes(tree: ast.Module) -> set[str]:
    """Classes of this module that hold mutable state: a method rebinds a `self` attribute, or `__init__` binds a container
    to `self.<attr>` that some code in the module mutates in place (a built-once value object such as a fold table is not state)."""
    mutated = _mutated_attributes(tree)
    found: set[str] = set()
    for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
        for method in (m for m in cls.body if isinstance(m, ast.FunctionDef | ast.AsyncFunctionDef)):
            for node in ast.walk(method):
                targets = (
                    node.targets
                    if isinstance(node, ast.Assign)
                    else [node.target]
                    if isinstance(node, ast.AnnAssign | ast.AugAssign)
                    else []
                )
                for t in targets:
                    if not (isinstance(t, ast.Attribute) and ast.unparse(t.value) == "self"):
                        continue
                    if method.name != "__init__" or (_is_container(getattr(node, "value", None)) and t.attr in mutated):
                        found.add(cls.name)
    return found


def _global_state(source: Source) -> Iterator[Hit]:
    """The line of each import-time I/O call, `global` statement and function-mutated module container."""
    tree = source.tree
    for node in _import_time(tree.body):
        if _is_io(node):
            yield source.rel, node.lineno
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            yield source.rel, node.lineno
    containers = _module_containers(tree)
    callees = {"next"} | {n.name for n in tree.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)}
    mutated: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            mutated |= _mutated_in(node, containers, callees)
    yield from ((source.rel, containers[name]) for name in sorted(mutated))
    stateful = _stateful_classes(tree)
    for node in _import_time(tree.body):
        if isinstance(node, ast.Assign | ast.AnnAssign) and isinstance(node.value, ast.Call) and ast.unparse(node.value.func) in stateful:
            yield source.rel, node.lineno


def _rows(reason: str, *paths: tuple[str, int]) -> dict[str, Row]:
    return rows(reason, *((f"packages/{path}", count) for path, count in paths))


_ALLOWED = {
    **_rows(
        "outcome: the children this process spawned detached and has not yet reaped: the process table is per process by nature, and a "
        "dropped Popen leaves a zombie and a ResourceWarning; reaped on the next spawn",
        ("stream-proc/src/stream_proc/detach.py", 1),
    ),
    # --- debt: global state still owed a conversion to an injected collaborator ---
    **_rows(
        "debt: a lazy builtins cache rebound by `global` and an extension dict, both reset by `reset_for_testing`; an injected "
        "registry object the caller builds and passes (the reset hook is the smell)",
        ("a2effect/src/a2effect/raises_registry.py", 3),
    ),
    **_rows(
        "debt: a once-per-process memo of the sandbox probe (`_probed`); the caller holds the result, or `preflight` takes it",
        ("any-agent/src/any_agent/harnesses/opencode_sandbox.py", 1),
    ),
    **_rows(
        "debt: a process-wide lock table keyed by (checkout, bead, key); an owner object per client holds its own locks",
        ("beads-client/src/beads_client/client.py", 1),
    ),
    **_rows(
        "debt: the fake store's id counter (`itertools.count`) is shared by every fake repo in the process; a counter per store",
        ("git-porcelain/src/git_porcelain/fake_store.py", 1),
    ),
    **_rows(
        "debt: a process-wide warn-once set; the middleware instance owns its own seen-set",
        ("mcp-result-wire/src/mcp_result_wire/_format_routing.py", 1),
        ("mcp-result-wire/src/mcp_result_wire/_list_view.py", 1),
    ),
    **_rows(
        "debt: a process-wide savepoint-name counter; the connection wrapper owns it",
        ("sqlite-sidecar/src/sqlite_sidecar/__init__.py", 1),
    ),
    **_rows(
        "debt: a process-wide set of already schema-checked databases; the store object remembers what it checked",
        ("sqlite-store/src/sqlite_store/store.py", 1),
    ),
    **_rows(
        "debt: a process-wide mount-verdict cache with its own fork hook (`clear_filesystem_cache` is the test reset); the store owns it",
        ("sqlite-store/src/sqlite_store/filesystem.py", 2),
    ),
    **_rows(
        "debt: a module-level thread-local set of paths being updated (a re-entrancy guard); the document handle owns it",
        ("any-json-doc/src/any_json_doc/__init__.py", 1),
    ),
    **_rows(
        "debt: a process-wide table of held logs (`HELD`) that callers cannot replace; the caller owns a `HeldLogs` and passes it",
        ("jsonl-log/src/jsonl_log/_held.py", 1),
    ),
    # --- outcome: module-level state that is the module's documented design ---
    **_rows(
        "outcome: a registry the module's public register call fills (`register_error_kind`); one table per process is its contract",
        ("a2effect/src/a2effect/errors.py", 1),
    ),
    **_rows(
        "outcome: the checkpoint registry filled at import by the `@check` decorator; the engine reads it as the catalog of checks",
        ("blueprint/src/blueprint/model.py", 1),
    ),
    **_rows(
        "outcome: a `flock` belongs to the process, so the table of held locks is process-wide by the operation's nature",
        ("process-lock/src/process_lock/__init__.py", 1),
    ),
    **_rows(
        "outcome: connections belong to the process; the weak registry, its `atexit` close and its fork hook exist so no instance "
        "leaks a connection into a child or past exit",
        ("sqlite-store/src/sqlite_store/connections.py", 3),
    ),
}

MODULE_LEVEL_STATE = Rule(
    "module-level-state",
    "module-level I/O or global mutable state (pass the collaborator in at the edge, or add a reasoned row)",
    _global_state,
    _ALLOWED,
    ("outcome", "debt"),
    debt_until=DEBT_UNTIL,
)


def test_repo_has_exactly_the_module_level_state_its_rows_list() -> None:
    check(MODULE_LEVEL_STATE, _ROOT)


@pytest.mark.parametrize(
    ("source", "count"),
    [
        ("data = open('x').read()\n", 1),
        ("import os\nHOME = os.environ['HOME']\n", 1),
        ("import os\nHOME = os.environ.get('HOME')\n", 1),
        ("import subprocess\nOUT = subprocess.run(['ls'])\n", 1),
        ("from pathlib import Path\nTEXT = Path('x').read_text()\n", 1),
        ("class A:\n    TEXT = open('x').read()\n", 1),
        ("if True:\n    data = open('x')\n", 1),
        ("import atexit\natexit.register(print)\n", 1),
        ("_n = 0\ndef bump():\n    global _n\n    _n += 1\n", 1),
        ("_seen = {}\ndef note(k):\n    _seen[k] = 1\n", 1),
        ("_seen = []\ndef note(k):\n    _seen.append(k)\n", 1),
        ("_seen = set()\ndef note(k):\n    fill(_seen, k)\ndef fill(s, k):\n    s.add(k)\n", 1),
        ("from itertools import count\n_ids = count()\ndef new():\n    return next(_ids)\n", 1),
        (
            "class Reg:\n    def __init__(self):\n        self.items = {}\n    def add(self, k):\n        self.items[k] = 1\nREG = Reg()\n",
            1,
        ),
        ("class Cur:\n    def bump(self):\n        self.n = 1\nCUR = Cur()\n", 1),
        (
            "class F:\n    def __init__(self, t):\n        self.t = {}\n        for k in t:\n            self.t[k] = 1\nFOLD = F({})\n",
            0,
        ),
        ("class Marker:\n    pass\nMARK = Marker()\n", 0),
        ("def read():\n    return open('x').read()\n", 0),
        ("import os\ndef home():\n    return os.environ['HOME']\n", 0),
        ("TABLE = {'a': 1}\ndef get(k):\n    return TABLE[k]\n", 0),
        ("TABLE = {'a': 1}\nTABLE['b'] = 2\n", 0),
        ("_seen = []\ndef note(k):\n    _seen = []\n    _seen.append(k)\n    return _seen\n", 0),
        ("_seen = {}\ndef size():\n    return len(_seen)\n", 0),
        ("ARGS = ['a']\ndef go(run):\n    return run(ARGS)\n", 0),
        ("import functools\n@functools.cache\ndef f():\n    return open('x').read()\n", 0),
    ],
)
def test_the_scanner_sees_what_it_claims_to(tmp_path: Path, source: str, count: int) -> None:
    assert sum(len(lines) for lines in plant(MODULE_LEVEL_STATE, tmp_path, source).values()) == count


def test_a_planted_open_in_a_scratch_package_is_found_by_line(tmp_path: Path) -> None:
    found = plant(MODULE_LEVEL_STATE, tmp_path, "import json\n\nCONFIG = json.load(open('c.json'))\n", path="packages/p/src/p/m.py")
    assert found == {"packages/p/src/p/m.py": [3]}
