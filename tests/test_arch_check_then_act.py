"""No check-then-act (constitution Article III, "Two kinds of failure"): TOCTOU on a path.

`if not p.exists(): p.mkdir()` and `if p.exists(): p.unlink()` ask the filesystem, then act on the answer; between the two
another process can change it. The act itself says what happened (`mkdir` raises `FileExistsError`, `unlink` raises
`FileNotFoundError`, `open(p, "x")` creates exclusively): call it and handle that exception.

A hit is an `if` whose test calls `os.path.exists` / `isfile` / `isdir` / `lexists` / `islink`, `os.access`, or
`.exists()` / `.is_file()` / `.is_dir()` / `.is_symlink()` on a path expression P, and whose guarded region mutates the same P:

- the guarded region is the whole `if` (both branches), plus the statements after it in the same block when the `if` body
  ends with `return` / `raise` / `continue` / `break` and has no `else` (the early-exit form: `if not p.exists(): return`);
- a mutation is `P.mkdir` / `unlink` / `rmdir` / `rename` / `replace` / `touch` / `write_text` / `write_bytes` / `symlink_to`,
  `P.open(mode)` or `open(P, mode)` with a write mode (`w`, `a`, `x`, `+`), `os.open(P, ..)` with a create or a write flag,
  `os.remove` / `unlink` / `rename` / `replace` / `mkdir` / `makedirs` / `rmdir` / `truncate` / `symlink` / `link` on P, and
  `shutil.copy*(src, P)` (a copy's source is only read), `shutil.move(P, ..)` / `move(.., P)`, `shutil.rmtree(P)` and the other
  one-path verbs.

P is compared as source text (`ast.unparse`), so `p` and `self.path` match only themselves: a derived path (`p.parent`,
`p / "x"`) or an alias (`q = p`) is not followed. A check whose only guarded use is a read is not a hit.

Checked over `packages/*/src` (tests excluded). Row key `file:Class.function`. `debt:` a real race (fix: do the act and catch
the typed error); `outcome:` the race is closed another way (a lock held across both, one owner of the path, a fresh private
directory) or is harmless (the act is idempotent and the check is an optimisation).
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from any_arch import Rule, check, plant, rows

from tests.arch_keys import qualnames

if TYPE_CHECKING:
    from collections.abc import Iterator

    from any_arch import Hit, Source

_ROOT = Path(__file__).resolve().parent.parent
_CHECK_METHODS = {"exists", "is_file", "is_dir", "is_symlink"}
_CHECK_FUNCS = {"os.path.exists", "os.path.isfile", "os.path.isdir", "os.path.lexists", "os.path.islink", "os.access"}
_PATH_MUTATORS = {"mkdir", "unlink", "rmdir", "rename", "replace", "touch", "write_text", "write_bytes", "symlink_to"}
_OS_MUTATORS = {"remove", "unlink", "rename", "replace", "mkdir", "makedirs", "rmdir", "truncate", "symlink", "link"}
_EXITS = ast.Return | ast.Raise | ast.Continue | ast.Break


def _checked(test: ast.expr) -> set[str]:
    """The path expressions the test asks the filesystem about."""
    paths: set[str] = set()
    for node in ast.walk(test):
        if not isinstance(node, ast.Call):
            continue
        name = ast.unparse(node.func)
        if isinstance(node.func, ast.Attribute) and node.func.attr in _CHECK_METHODS and not node.args:
            paths.add(ast.unparse(node.func.value))
        elif (name in _CHECK_FUNCS or name.endswith(("path.exists", "path.isfile", "path.isdir"))) and node.args:
            paths.add(ast.unparse(node.args[0]))
    return paths


def _writes(mode: ast.expr | None) -> bool:
    return isinstance(mode, ast.Constant) and isinstance(mode.value, str) and any(c in mode.value for c in "wax+")


def _mode(call: ast.Call, position: int) -> ast.expr | None:
    keyword = next((k.value for k in call.keywords if k.arg == "mode"), None)
    return keyword if keyword is not None else (call.args[position] if len(call.args) > position else None)


def _method_mutated(call: ast.Call, func: ast.Attribute) -> set[str]:
    receiver = ast.unparse(func.value)
    if func.attr in _PATH_MUTATORS and receiver not in {"os", "shutil"}:
        return {receiver}
    if func.attr == "open" and receiver not in {"os", "io", "gzip", "bz2", "lzma"} and _writes(_mode(call, 0)):
        return {receiver}
    return set()


def _mutated(call: ast.Call) -> set[str]:
    """The path expressions this call changes on disk."""
    func = call.func
    name = ast.unparse(func)
    args = [ast.unparse(a) for a in call.args]
    found = _method_mutated(call, func) if isinstance(func, ast.Attribute) else set()
    if name in {"open", "io.open"} and args and _writes(_mode(call, 1)):
        found.add(args[0])
    if name == "os.open" and args and any(w in ast.unparse(call) for w in ("O_CREAT", "O_WRONLY", "O_RDWR")):
        found.add(args[0])
    if name.startswith("os.") and name.removeprefix("os.") in _OS_MUTATORS:
        found.update(args[:2])
    if name.startswith("shutil."):
        verb = name.removeprefix("shutil.")
        found.update(args[1:2] if verb.startswith("copy") else args[:2] if verb == "move" else args[:1])  # a copy changes only its target
    return found


def _mutations(statements: list[ast.stmt]) -> set[str]:
    found: set[str] = set()
    stack: list[ast.AST] = list(statements)
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Call):
            found |= _mutated(node)
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda | ast.ClassDef):
            stack.extend(ast.iter_child_nodes(node))
    return found


def _blocks(tree: ast.Module) -> Iterator[list[ast.stmt]]:
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list) and block and isinstance(block[0], ast.stmt):
                yield block


def _raced(source: Source) -> Iterator[Hit]:
    names = qualnames(source.tree)
    for block in _blocks(source.tree):
        for index, statement in enumerate(block):
            if not isinstance(statement, ast.If):
                continue
            checked = _checked(statement.test)
            if not checked:
                continue
            region = [statement]
            if not statement.orelse and isinstance(statement.body[-1], _EXITS):
                region += block[index + 1 :]
            if checked & _mutations(region):
                yield f"{source.rel}:{names[statement]}", statement.lineno


_ALLOWED = {
    **rows(
        "debt: `exists()` then `rename` / `replace` on a path another process can remove in between (rotation, SQLite deleting "
        "`-wal` / `-shm` when its last connection closes); do the rename and catch FileNotFoundError",
        ("packages/any-proc/src/any_proc/supervise.py:rotate_log", 2),
        ("packages/sqlite-sidecar/src/sqlite_sidecar/__init__.py:move_aside", 1),
    ),
    **rows(
        "debt: create-if-absent by `exists()` then `write_text`, so a file made in between is overwritten; "
        "`open(target, 'x')` and catch FileExistsError says what is meant (never clobber)",
        ("packages/any-knowledge/src/any_knowledge/templates.py:install", 1),
    ),
    **rows(
        "outcome: the race is closed another way: the act runs under the lock, or the path has one owner for the run "
        "(a vendor install into its own staging name, a record file only this command writes) and the act tolerates absence",
        ("packages/any-mailbox/src/any_mailbox/__init__.py:Mailbox.take", 1),
        ("packages/any-gate/src/any_gate/state.py:GateState.passed", 1),
        ("packages/launchd-agent/src/launchd_agent/__init__.py:uninstall", 1),
        ("packages/shelf-vendor/src/shelf_vendor/__init__.py:_install", 2),
    ),
    **rows(
        "outcome: read, compare, write the same bytes: the check only skips a redundant idempotent write, and the file has one writer",
        ("packages/blueprint/src/blueprint/render.py:write", 1),
        ("packages/blueprint/src/blueprint/report.py:_write", 1),
    ),
}

TOCTOU = Rule(
    "check-then-act",
    "a path is tested, then changed on the strength of the answer (do the act and catch FileExistsError / FileNotFoundError, "
    "or add a reasoned row)",
    _raced,
    _ALLOWED,
    ("debt", "outcome"),
)


def test_repo_checks_then_acts_exactly_where_its_rows_list() -> None:
    check(TOCTOU, _ROOT)


@pytest.mark.parametrize(
    "body",
    [
        "if not p.exists():\n    p.mkdir()\n",
        "if p.exists():\n    p.unlink()\n",
        "if not os.path.exists(path):\n    os.makedirs(path)\n",
        "if os.path.isfile(path):\n    os.remove(path)\n",
        "if not self.path.is_dir():\n    self.path.mkdir(parents=True)\n",
        "if not p.exists():\n    p.write_text('x')\n",
        "if not p.exists():\n    with open(p, 'w') as fh:\n        fh.write('x')\n",
        "if not p.exists():\n    with p.open('a') as fh:\n        fh.write('x')\n",
        "if p.is_file() and ok():\n    shutil.move(p, q)\n",
        "if q.exists():\n    shutil.copyfile(p, q)\n",
        "if p.exists():\n    shutil.rmtree(p)\n",
        "if not p.exists():\n    return\np.unlink()\n",
        "if not os.access(path, os.W_OK):\n    raise OSError\nos.replace(tmp, path)\n",
        "if p.exists():\n    pass\nelse:\n    p.touch()\n",
    ],
)
def test_a_planted_check_then_act_is_found(tmp_path: Path, body: str) -> None:
    source = "def g(p, path, tmp, q):\n" + "".join(f"    {line}\n" for line in body.splitlines())
    found = plant(TOCTOU, tmp_path, source)
    assert list(found) == ["packages/pkg/src/pkg/mod.py:g"]
    assert len(found["packages/pkg/src/pkg/mod.py:g"]) == 1


@pytest.mark.parametrize(
    "body",
    [
        "if p.exists():\n    return p.read_text()\n",
        "if not p.exists():\n    return None\nreturn p.read_text()\n",
        "if p.exists():\n    q.unlink()\n",
        "if p.is_file():\n    shutil.copy2(p, q)\n",
        "if p.exists():\n    with open(p) as fh:\n        return fh.read()\n",
        "if p.exists():\n    with p.open('rb') as fh:\n        return fh.read()\n",
        "if p.exists():\n    log(p)\nelse:\n    q.mkdir()\n",
        "p.mkdir(exist_ok=True)\n",
        "if ready():\n    p.unlink()\n",
        "if not p.exists():\n    log()\np.unlink()\n",
    ],
)
def test_a_read_a_different_path_or_no_check_is_not_a_hit(tmp_path: Path, body: str) -> None:
    source = "def g(p, path, tmp, q):\n" + "".join(f"    {line}\n" for line in body.splitlines())
    assert plant(TOCTOU, tmp_path, source) == {}
