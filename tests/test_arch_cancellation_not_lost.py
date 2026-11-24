"""Cancellation is not lost (constitution Article III, "Two kinds of failure").

`asyncio.CancelledError`, `KeyboardInterrupt`, `SystemExit` and `GeneratorExit` are control flow: swallowing one turns a
cancel or an interrupt into a normal return, and the task never stops. A hit is a handler that can catch one

- `except BaseException`, `except asyncio.CancelledError` / `except CancelledError`, `except KeyboardInterrupt`,
  `except SystemExit`, `except GeneratorExit`, or a bare `except:` (also inside a tuple),

and does not raise on every path. A handler raises on every path when one of its statements is `raise` (bare, or a new
exception), an `if`/`else` whose branches both raise, a `with` whose body does, or a `try` whose `finally` does. A `raise` in only
one branch, or a handler that stores the exception and re-raises later, is a hit: read it and mark `outcome:` when the
later raise is real.

Checked over `packages/*/src` (tests excluded). Rows: file -> (hit count, reason). `debt:` is a handler that loses a cancel
(fix: re-raise, or catch `Exception`); `outcome:` the catch is the point (the process edge turns the signal into an exit
code; the exception is stored and re-raised after cleanup, which the finder cannot see).
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from any_arch import Rule, check, plant, rows

if TYPE_CHECKING:
    from collections.abc import Iterator

    from any_arch import Hit, Source

_ROOT = Path(__file__).resolve().parent.parent
_CONTROL_FLOW = {"BaseException", "CancelledError", "KeyboardInterrupt", "SystemExit", "GeneratorExit"}


def _catches_control_flow(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(ast.unparse(t).split(".")[-1] in _CONTROL_FLOW for t in types)


def _always_raises(body: list[ast.stmt]) -> bool:
    for statement in body:
        if isinstance(statement, ast.Raise):
            return True
        if isinstance(statement, ast.If) and statement.orelse and _always_raises(statement.body) and _always_raises(statement.orelse):
            return True
        if isinstance(statement, ast.With | ast.AsyncWith) and _always_raises(statement.body):
            return True
        if isinstance(statement, ast.Try) and _always_raises(statement.finalbody):
            return True
    return False


def _lost(source: Source) -> Iterator[Hit]:
    for node in ast.walk(source.tree):
        if isinstance(node, ast.ExceptHandler) and _catches_control_flow(node) and not _always_raises(node.body):
            yield source.rel, node.lineno


_ALLOWED = {
    **rows(
        "outcome: the exception is kept and raised after the stop finished (`_try` returns it, `_stop_error` raises it), "
        "so the cancel is delayed by the stop, not lost",
        ("packages/any-agent/src/any_agent/supervisor.py", 1),
    ),
    **rows(
        "outcome: every failure and cancel is collected and re-raised together by `raise_failures`, so the cancel is not lost",
        ("packages/async-scope/src/async_scope/__init__.py", 2),
        ("packages/async-scope/src/async_scope/cleanup.py", 2),
    ),
    **rows(
        "outcome: the failure is stored and raised on the owner by release; the pipes must keep draining meanwhile",
        ("packages/stream-proc/src/stream_proc/pump.py", 2),
    ),
    **rows(
        "outcome: `SystemExit` here is argparse rejecting its own input inside the call; the usage message is the answer",
        ("packages/argparse-mcp/src/argparse_mcp/tools.py", 1),
        ("packages/verb-cli/src/verb_cli/testing.py", 1),
        ("packages/blueprint/src/blueprint/testing.py", 1),
    ),
}

LOST = Rule(
    "cancellation-not-lost",
    "a handler of BaseException / CancelledError / KeyboardInterrupt swallows a cancel (re-raise it, or catch Exception, or add a "
    "reasoned row)",
    _lost,
    _ALLOWED,
    ("debt", "outcome"),
)


def test_repo_loses_exactly_the_cancellations_its_rows_list() -> None:
    check(LOST, _ROOT)


@pytest.mark.parametrize(
    "source",
    [
        "try:\n    f()\nexcept BaseException:\n    log()\n",
        "try:\n    f()\nexcept:\n    pass\n",
        "async def g():\n    try:\n        await f()\n    except asyncio.CancelledError:\n        return None\n",
        "try:\n    f()\nexcept CancelledError:\n    cleanup()\n",
        "try:\n    f()\nexcept (OSError, KeyboardInterrupt):\n    return 1\n",
        "try:\n    f()\nexcept BaseException as e:\n    if ok(e):\n        raise\n",
        "try:\n    f()\nexcept BaseException as e:\n    saved = e\n",
        "try:\n    f()\nexcept SystemExit:\n    code = 1\n",
    ],
)
def test_a_planted_swallowed_cancellation_is_found(tmp_path: Path, source: str) -> None:
    found = plant(LOST, tmp_path, source)
    assert list(found) == ["packages/pkg/src/pkg/mod.py"]
    assert len(found["packages/pkg/src/pkg/mod.py"]) == 1


@pytest.mark.parametrize(
    "source",
    [
        "try:\n    f()\nexcept BaseException:\n    cleanup()\n    raise\n",
        "try:\n    f()\nexcept asyncio.CancelledError:\n    raise\n",
        "try:\n    f()\nexcept KeyboardInterrupt as e:\n    raise SystemExit(130) from e\n",
        (
            "try:\n    f()\nexcept BaseException as e:\n    if ok(e):\n        cleanup()\n        raise\n    else:\n        raise "
            "Wrapped() from e\n"
        ),
        "try:\n    f()\nexcept Exception:\n    pass\n",
        "try:\n    f()\nexcept (OSError, ValueError):\n    pass\n",
    ],
)
def test_a_reraise_or_an_ordinary_handler_is_not_a_hit(tmp_path: Path, source: str) -> None:
    assert plant(LOST, tmp_path, source) == {}
