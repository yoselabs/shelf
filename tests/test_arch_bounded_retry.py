"""Bounded retry (constitution Article III, "Two kinds of failure"): a retry loop has an attempt count or a deadline.

A loop that catches a failure, sleeps and tries again with nothing that ends it turns a permanent failure (a wrong
password, a missing binary, a full disk) into a hang. The retry belongs to one primitive with a budget; a hand-made loop
needs the same bound.

A hit is a `while` loop whose test is `True`, a bare name or attribute (a flag), or `not` of one, a name, attribute or
call (`while not stop.is_set()`), and whose body (nested functions excluded)

- has a `try` with a handler that can fall through to the next turn: not every path of it ends in `raise`, `return` or `break`
  (`if not retryable(e): raise` alone does not leave it),
- calls a sleep (`sleep`, `*.sleep`, `*_sleep`, `*.wait(timeout)`) or something named `backoff` / `delay`, and
- shows no bound: no counter step (`n += 1`, `n = n + 1`), no comparison that names an attempt / retry / tries / deadline /
  max / limit / budget / remaining / elapsed / timeout, no clock read (`monotonic()`, `time()`, `perf_counter()`).

A loop that sleeps without catching (a poll) and a `for attempt in range(n)` loop are not hits. Row key
`file:Class.function`. `debt:` a real unbounded retry (fix: the retry primitive with a budget, or a deadline); `outcome:` the
loop is a daemon or a worker that is meant to run until stopped, so "again" is its job, not a retry, and its flag is the bound.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from any_arch import Rule, check, plant, rows

from tests.arch_keys import qualnames

if TYPE_CHECKING:
    from collections.abc import Iterator

    from any_arch import Hit, Source

_ROOT = Path(__file__).resolve().parent.parent
_BOUND_NAME = re.compile(r"attempt|retr(y|ies)|tries|deadline|max|limit|budget|remaining|elapsed|timeout", re.IGNORECASE)
_CLOCKS = {"monotonic", "time", "perf_counter", "monotonic_ns", "time_ns"}
_LEAVES = ast.Raise | ast.Return | ast.Break


def _own(statements: list[ast.stmt]) -> Iterator[ast.AST]:
    stack: list[ast.AST] = list(statements)
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda | ast.ClassDef):
            stack.extend(ast.iter_child_nodes(node))


def _open_ended(test: ast.expr) -> bool:
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return isinstance(test.operand, ast.Name | ast.Attribute | ast.Call)
    return (isinstance(test, ast.Constant) and test.value is True) or isinstance(test, ast.Name | ast.Attribute)


def _leaves(body: list[ast.stmt]) -> bool:
    """Whether every path through `body` ends in `raise`, `return` or `break` (a conditional one does not count)."""
    for statement in body:
        if isinstance(statement, _LEAVES):
            return True
        if isinstance(statement, ast.If) and statement.orelse and _leaves(statement.body) and _leaves(statement.orelse):
            return True
    return False


def _retries(nodes: list[ast.AST]) -> bool:
    return any(isinstance(node, ast.Try) and any(not _leaves(handler.body) for handler in node.handlers) for node in nodes)


def _sleeps(nodes: list[ast.AST]) -> bool:
    for node in nodes:
        if isinstance(node, ast.Call):
            name = ast.unparse(node.func)
            last = name.split(".")[-1]
            if last.endswith("sleep") or last.startswith(("backoff", "delay")) or (last == "wait" and (node.args or node.keywords)):
                return True
    return False


def _self_increment(node: ast.AST) -> bool:
    """`n = n + 1`"""
    if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Add)):
        return False
    return any(ast.unparse(target) == ast.unparse(node.value.left) for target in node.targets)


def _bounded(nodes: list[ast.AST]) -> bool:
    for node in nodes:
        if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add):
            return True
        if _self_increment(node):
            return True
        if isinstance(node, ast.Compare) and _BOUND_NAME.search(ast.unparse(node)):
            return True
        if isinstance(node, ast.Call) and ast.unparse(node.func).split(".")[-1] in _CLOCKS:
            return True
    return False


def _unbounded(source: Source) -> Iterator[Hit]:
    names = qualnames(source.tree)
    for node in ast.walk(source.tree):
        if isinstance(node, ast.While) and _open_ended(node.test):
            inside = list(_own(node.body))
            if _retries(inside) and _sleeps(inside) and not _bounded([*inside, *ast.walk(node.test)]):
                yield f"{source.rel}:{names[node]}", node.lineno


_ALLOWED = {
    **rows(
        "outcome: not a retry: a short slice of `child.wait` so a Python signal handler runs (and, in the supervisor, a deadline "
        "and the parent are checked); the loop ends when the child exits",
        ("packages/any-lease/src/any_lease/__main__.py:_run", 1),
        ("packages/any-agent/src/any_agent/supervisor.py:Supervisor._wait", 1),
    ),
}

UNBOUNDED = Rule(
    "bounded-retry",
    "a retry loop has no attempt count or deadline (bound it, or use the retry primitive, or add a reasoned row)",
    _unbounded,
    _ALLOWED,
    ("debt", "outcome"),
)


def test_repo_retries_without_a_bound_exactly_where_its_rows_list() -> None:
    check(UNBOUNDED, _ROOT)


@pytest.mark.parametrize(
    "loop",
    [
        "while True:\n    try:\n        return f()\n    except OSError:\n        time.sleep(1)\n",
        "while True:\n    try:\n        f()\n        break\n    except OSError:\n        continue\n    time.sleep(0.1)\n",
        (
            "while True:\n    try:\n        return f()\n    except OSError as e:\n        if not retryable(e):\n            raise\n    "
            "time.sleep(1)\n"
        ),
        "while not done:\n    try:\n        f()\n    except OSError:\n        pass\n    await asyncio.sleep(2)\n",
        "while ok:\n    try:\n        f()\n    except OSError:\n        log()\n    backoff()\n",
        "while not stop.is_set():\n    try:\n        f()\n    except Exception:\n        log()\n    stop.wait(5)\n",
        "while self.running:\n    try:\n        f()\n    except OSError:\n        delay = delay * 2\n        sleep(delay)\n",
    ],
)
def test_a_planted_unbounded_retry_is_found(tmp_path: Path, loop: str) -> None:
    source = "def g():\n" + "".join(f"    {line}\n" for line in loop.splitlines())
    assert plant(UNBOUNDED, tmp_path, source) == {"packages/pkg/src/pkg/mod.py:g": [2]}


@pytest.mark.parametrize(
    "loop",
    [
        "while True:\n    try:\n        return f()\n    except OSError:\n        tries += 1\n        time.sleep(1)\n",
        (
            "while True:\n    try:\n        return f()\n    except OSError:\n        if time.monotonic() > end:\n            raise\n     "
            "   time.sleep(1)\n"
        ),
        (
            "while True:\n    try:\n        return f()\n    except OSError:\n        if attempt >= 5:\n            raise\n        "
            "time.sleep(1)\n"
        ),
        "while True:\n    try:\n        return f()\n    except OSError:\n        raise\n    time.sleep(1)\n",
        (
            "while True:\n    try:\n        return f()\n    except OSError as e:\n        if e.errno == 1:\n            raise\n        "
            "else:\n            return None\n    time.sleep(1)\n"
        ),
        "while True:\n    try:\n        return f()\n    except OSError:\n        break\n    time.sleep(1)\n",
        "while True:\n    if ready():\n        return\n    time.sleep(1)\n",
        "while True:\n    try:\n        return f()\n    except OSError:\n        log()\n",
        "while n < 5:\n    try:\n        return f()\n    except OSError:\n        time.sleep(1)\n",
        "for attempt in range(5):\n    try:\n        return f()\n    except OSError:\n        time.sleep(1)\n",
    ],
)
def test_a_bounded_loop_a_poll_or_a_raising_handler_is_not_a_hit(tmp_path: Path, loop: str) -> None:
    source = "def g():\n" + "".join(f"    {line}\n" for line in loop.splitlines())
    assert plant(UNBOUNDED, tmp_path, source) == {}
