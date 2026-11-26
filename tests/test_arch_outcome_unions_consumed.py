"""Outcome unions are consumed (constitution Article III, "Two kinds of failure").

An expected outcome is a union in the return type (`Rebased | Conflict`). The union lets a caller narrow; it does not force
the caller to look: discarding the value is legal and pyrefly's unused-call-result is off. This rule closes that gap.

An *outcome type* is a frozen dataclass defined in `packages/*/src`. An *outcome union* is a return annotation with at least two
outcome types among its members (`A | B`, `Union[A, B]`, `A | B | None`, a quoted annotation, or a module-level alias of one;
`X | None` and unions of builtins never count). A hit is a call to a function with such a return annotation that is

- a bare expression statement (or `_ = call()`): the value is dropped, or
- assigned to a name that is never narrowed after the assignment, in the same scope: no `match x`, `isinstance(x, ..)`,
  `type(x)`, `x.attr`, `x is ..` / `x == ..`, and not returned or yielded (a wrapper delegates the duty to its own caller), or
- the subject of a `match` that names only some of the union's classes and has no `case _` / capture case to close it.

How a callee is resolved (static, no types, `packages/*/src` only, tests excluded):

- `f(...)`: `f` is a top-level function of this module, or imported with `from <package module> import f [as g]`
- `mod.f(...)`: `mod` is an imported shelf module, `f` a top-level function in it
- `obj.m(...)` and `self.m(...)`: resolved by the method name alone, only if EVERY `def m` in the whole `packages/*/src`
  tree (functions, methods, protocol stubs, fakes) has an outcome-union return. One plain `def m` elsewhere removes the name.

Limits, stated so nobody trusts it past them: no data flow (a callee passed as a value, `partial`, a call behind `getattr`,
or a value moved through a container is not followed); an `if isinstance` chain is not checked for exhaustiveness (only `match`);
a name narrowed anywhere after the assignment counts as narrowed even if another assignment to the same name is not.
pyrefly `--report-pysa` resolves 96.7% of calls but is minutes slow; this rule is seconds and is deliberately narrower.

Rows: file -> (hit count, reason). `debt:` is a real discard still owed a fix; `outcome:` the discard is the answer.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from any_arch import Row, Rule, check, plant, rows
from any_arch.source import sources

from tests.arch_keys import DEBT_UNTIL

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from any_arch import Hit, Source

_ROOT = Path(__file__).resolve().parent.parent
_SCOPE = ("packages/*/src/**/*.py",)
_Def = ast.FunctionDef | ast.AsyncFunctionDef


def _frozen(node: ast.ClassDef) -> bool:
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call) and ast.unparse(decorator.func).endswith("dataclass"):
            return any(k.arg == "frozen" and isinstance(k.value, ast.Constant) and k.value.value is True for k in decorator.keywords)
    return False


def _members(annotation: ast.expr | None) -> list[str]:
    """The simple names an annotation is a union of; subscripts are stripped (`Present[T]` -> `Present`)."""
    if annotation is None:
        return []
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        return _members(annotation.left) + _members(annotation.right)
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        try:
            return _members(ast.parse(annotation.value, mode="eval").body)
        except SyntaxError:
            return []
    head = ast.unparse(annotation.value if isinstance(annotation, ast.Subscript) else annotation).split(".")[-1]
    if isinstance(annotation, ast.Subscript) and head in {"Union", "Optional"}:
        inner = annotation.slice
        return [m for part in (inner.elts if isinstance(inner, ast.Tuple) else [inner]) for m in _members(part)]
    return [head]


class _Index:
    """What the whole tree says: outcome types, union aliases, and for each function name the outcome unions of its defs."""

    def __init__(self, root: Path) -> None:
        trees = {s.rel: s for s in sources(root, _SCOPE)}
        self.outcomes = {n.name for s in trees.values() for n in ast.walk(s.tree) if isinstance(n, ast.ClassDef) and _frozen(n)}
        self.aliases: dict[str, list[str]] = {}
        for _ in range(3):  # aliases of aliases
            for s in trees.values():
                for n in s.tree.body:
                    target, value = _alias(n)
                    if target and len(set(self.expand(_members(value))) & self.outcomes) >= 2:
                        self.aliases[target] = _members(value)
        by_name: dict[str, list[tuple[str, ...]]] = {}  # def name -> the outcomes of every def of it ((): not an outcome union)
        self.top: dict[tuple[str, str], tuple[str, ...]] = {}  # (module path no .py, function) -> outcomes of a top-level function
        for s in trees.values():
            for n in ast.walk(s.tree):
                if isinstance(n, _Def):
                    union = self.union(n.returns)
                    by_name.setdefault(n.name, []).append(union)
                    if n in s.tree.body and union:
                        self.top[(_module(s.rel), n.name)] = union
        self.methods = {name: defs[0] for name, defs in by_name.items() if all(defs)}  # every def of the name is an outcome union

    def expand(self, names: Iterable[str]) -> list[str]:
        return [m for name in names for m in (self.expand(self.aliases[name]) if name in self.aliases else [name])]

    def union(self, annotation: ast.expr | None) -> tuple[str, ...]:
        found = [m for m in self.expand(_members(annotation)) if m in self.outcomes]
        return tuple(dict.fromkeys(found)) if len(set(found)) >= 2 else ()


def _alias(node: ast.stmt) -> tuple[str | None, ast.expr | None]:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id, node.value
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id, node.value
    if isinstance(node, ast.TypeAlias):
        return node.name.id, node.value
    return None, None


def _module(rel: str) -> str:
    """`packages/p/src/p/m.py` -> `p.m`; `packages/p/src/p/__init__.py` -> `p`."""
    parts = Path(rel).with_suffix("").parts[3:]
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _imports(source: Source) -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    """from-imports `local -> (module, name)` and module imports `local -> module`, top level and nested alike."""
    names: dict[str, tuple[str, str]] = {}
    modules: dict[str, str] = {}
    for n in ast.walk(source.tree):
        if isinstance(n, ast.ImportFrom) and n.module and not n.level:
            for a in n.names:
                names[a.asname or a.name] = (n.module, a.name)
                modules[a.asname or a.name] = f"{n.module}.{a.name}"
        elif isinstance(n, ast.Import):
            for a in n.names:
                modules[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
    return names, modules


def _resolver(index: _Index, source: Source) -> Callable[[ast.expr], tuple[str, ...]]:
    names, modules = _imports(source)
    here = _module(source.rel)

    def resolve(func: ast.expr) -> tuple[str, ...]:
        if isinstance(func, ast.Name):
            if (here, func.id) in index.top:
                return index.top[here, func.id]
            module, name = names.get(func.id, ("", ""))
            return index.top.get((module, name), ())
        if isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name) and func.value.id in modules and (modules[func.value.id], func.attr) in index.top:
                return index.top[modules[func.value.id], func.attr]
            return index.methods.get(func.attr, ())
        return ()

    return resolve


def _scopes(tree: ast.Module) -> Iterable[ast.AST]:
    yield tree
    yield from (n for n in ast.walk(tree) if isinstance(n, _Def))


def _own(scope: ast.AST) -> Iterable[ast.AST]:
    """Nodes of `scope` without descending into nested function definitions."""
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, _Def | ast.Lambda | ast.ClassDef):
            stack.extend(ast.iter_child_nodes(node))


def _call(value: ast.expr | None) -> ast.Call | None:
    if isinstance(value, ast.Await):
        value = value.value
    return value if isinstance(value, ast.Call) else None


def _narrows(node: ast.AST, name: str) -> bool:
    def is_name(x: ast.AST | None) -> bool:
        return isinstance(x, ast.Name) and x.id == name

    if isinstance(node, ast.Match):
        return is_name(node.subject)
    if isinstance(node, ast.Call):
        return ast.unparse(node.func) in {"isinstance", "type"} and bool(node.args) and is_name(node.args[0])
    if isinstance(node, ast.Attribute):
        return is_name(node.value)
    if isinstance(node, ast.Compare):
        return any(is_name(x) for x in (node.left, *node.comparators))
    if isinstance(node, ast.Return | ast.Yield | ast.YieldFrom | ast.Await):
        return is_name(node.value)
    return False


def _covers(match: ast.Match, outcomes: tuple[str, ...]) -> bool:
    named: set[str] = set()
    for case in match.cases:
        patterns = case.pattern.patterns if isinstance(case.pattern, ast.MatchOr) else [case.pattern]
        for pattern in patterns:
            if isinstance(pattern, ast.MatchAs) and pattern.pattern is None and case.guard is None:
                return True  # `case _:` or a bare capture closes the match
            if isinstance(pattern, ast.MatchClass) and case.guard is None:
                named.add(ast.unparse(pattern.cls).split(".")[-1])
    return set(outcomes) <= named


def _assignments(
    nodes: list[ast.AST], resolve: Callable[[ast.expr], tuple[str, ...]]
) -> tuple[list[tuple[str, int, tuple[str, ...]]], list[int]]:
    """Names bound to a resolved call as `(name, line, outcomes)`, and the lines that bind one to `_`."""
    assigned: list[tuple[str, int, tuple[str, ...]]] = []
    discarded: list[int] = []
    for node in nodes:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign | ast.NamedExpr):
            targets, value = [node.target], node.value
        else:
            continue
        call = _call(value)
        outcomes = resolve(call.func) if call else ()
        for target in targets if outcomes else ():
            if isinstance(target, ast.Name) and target.id == "_":
                discarded.append(node.lineno)
            elif isinstance(target, ast.Name):
                assigned.append((target.id, node.lineno, outcomes))
    return assigned, discarded


def _unmatched(match: ast.Match, assigned: list[tuple[str, int, tuple[str, ...]]], resolve: Callable[[ast.expr], tuple[str, ...]]) -> bool:
    """Whether `match` is over a resolved outcome union and leaves a member unnamed with no closing case."""
    subject = match.subject
    known = resolve(subject.func) if isinstance(subject, ast.Call) else ()
    if isinstance(subject, ast.Name):
        prior = [(line, found) for name, line, found in assigned if name == subject.id and line < match.lineno]
        known = max(prior)[1] if prior else ()
    return bool(known) and not _covers(match, known)


def _unconsumed(scope: ast.AST, resolve: Callable[[ast.expr], tuple[str, ...]]) -> Iterable[int]:
    nodes = list(_own(scope))
    assigned, discarded = _assignments(nodes, resolve)
    yield from discarded
    for node in nodes:
        if isinstance(node, ast.Expr) and (call := _call(node.value)) and resolve(call.func):
            yield node.lineno
    everything = list(ast.walk(scope))
    for name, line, _ in assigned:
        if not any(_narrows(n, name) and getattr(n, "lineno", 0) >= line for n in everything):
            yield line
    yield from (n.lineno for n in nodes if isinstance(n, ast.Match) and _unmatched(n, assigned, resolve))


_FIX = "an outcome union is dropped or never narrowed (match it with `case _: assert_never(x)`, or add a reasoned row)"

_ALLOWED = {
    **rows(
        "debt: the fake `git clone` drops fetch's `Offline` and goes on as if the remote answered; return the failed "
        "CommandResult (or raise) when the result is `Offline`",
        ("packages/git-porcelain/src/git_porcelain/fake.py", 1),
    ),
    **rows(
        "debt: the fake `git fetch` with no refspec drops `fetch_once`'s `Offline` and reports ok=True; return the "
        "failed CommandResult when the result is `Offline`",
        ("packages/git-porcelain/src/git_porcelain/fake_remote.py", 1),
    ),
}


def _rule(root: Path, allowed: dict[str, Row]) -> Rule:
    return Rule("outcome-unions-consumed", _FIX, _finder(root), allowed, ("debt", "outcome"), _SCOPE, DEBT_UNTIL)


def _finder(root: Path) -> Callable[[Source], Iterable[Hit]]:
    built: list[_Index] = []  # indexed on the first file seen, so a planted file is part of it

    def find(source: Source) -> Iterable[Hit]:
        if not built:
            built.append(_Index(root))
        resolve = _resolver(built[0], source)
        for scope in _scopes(source.tree):
            for line in _unconsumed(scope, resolve):
                yield source.rel, line

    return find


OUTCOMES = _rule(_ROOT, _ALLOWED)  # module level, so `python -m any_arch` finds its `debt:` rows


def test_repo_drops_exactly_the_outcome_unions_its_rows_list() -> None:
    check(OUTCOMES, _ROOT)


_PRELUDE = """
from dataclasses import dataclass
from typing import Union

@dataclass(frozen=True)
class Rebased: ...
@dataclass(frozen=True)
class Conflict: ...
@dataclass(frozen=True)
class Gone: ...
Result = Rebased | Conflict

def rebase() -> Rebased | Conflict: ...
async def arebase() -> "Rebased | Conflict": ...
def aliased() -> Result: ...
def old_style() -> Union[Rebased, Conflict]: ...
def maybe() -> Rebased | None: ...
def plain() -> int | str: ...
class Repo:
    def rebase_it(self) -> Rebased | Conflict | Gone: ...
"""


@pytest.mark.parametrize(
    ("body", "lines"),
    [
        ("def f():\n    rebase()\n", [2]),
        ("async def f():\n    await arebase()\n", [2]),
        ("def f():\n    aliased()\n    old_style()\n", [2, 3]),
        ("def f():\n    _ = rebase()\n", [2]),
        ("def f():\n    r = rebase()\n    print(r)\n", [2]),
        ("def f(repo):\n    repo.rebase_it()\n", [2]),
        (
            (
                "def f(repo):\n    match repo.rebase_it():\n        case Rebased():\n            pass\n        case Conflict():\n        "
                "    pass\n"
            ),
            [2],
        ),
        ("def f():\n    r = rebase()\n    match r:\n        case Rebased():\n            pass\n", [3]),
    ],
)
def test_a_planted_dropped_or_unnarrowed_outcome_is_found(tmp_path: Path, body: str, lines: list[int]) -> None:
    found = plant(_rule(tmp_path, {}), tmp_path, _PRELUDE + body)
    offset = _PRELUDE.count("\n")
    assert found == {"packages/pkg/src/pkg/mod.py": [offset + n for n in lines]}


@pytest.mark.parametrize(
    "body",
    [
        "def f():\n    r = rebase()\n    if isinstance(r, Conflict):\n        return 1\n    return 0\n",
        "def f():\n    r = rebase()\n    return r.__class__\n",
        "def f():\n    return rebase()\n",
        "def f():\n    r = rebase()\n    return r\n",
        "def f():\n    r = rebase()\n    return r is not None\n",
        "def f():\n    match rebase():\n        case Rebased():\n            pass\n        case Conflict():\n            pass\n",
        "def f():\n    match rebase():\n        case Rebased():\n            pass\n        case _:\n            raise AssertionError\n",
        (
            "def f(repo):\n    match repo.rebase_it():\n        case Rebased() | Conflict():\n            pass\n        case Gone():\n   "
            "         pass\n"
        ),
        "def f():\n    maybe()\n    plain()\n    unknown()\n",
        "def f(callback):\n    callback()\n",
    ],
)
def test_a_consumed_or_non_outcome_call_is_not_a_hit(tmp_path: Path, body: str) -> None:
    assert plant(_rule(tmp_path, {}), tmp_path, _PRELUDE + body) == {}


def test_a_method_name_shared_with_a_plain_def_is_not_resolved(tmp_path: Path) -> None:
    source = _PRELUDE + "class Other:\n    def rebase_it(self) -> int: ...\ndef f(repo):\n    repo.rebase_it()\n"
    assert plant(_rule(tmp_path, {}), tmp_path, source) == {}


def test_a_callee_imported_from_another_package_is_resolved(tmp_path: Path) -> None:
    plant(_rule(tmp_path, {}), tmp_path, _PRELUDE, path="packages/lib/src/lib/ops.py")
    caller = "from lib.ops import rebase as go\nimport lib.ops as ops\n\ndef f():\n    go()\n    ops.rebase()\n"
    found = plant(_rule(tmp_path, {}), tmp_path, caller, path="packages/app/src/app/main.py")
    assert found == {"packages/app/src/app/main.py": [5, 6]}
