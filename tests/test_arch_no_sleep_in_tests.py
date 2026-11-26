"""No sleeping in tests: wait for the event or the condition, not for the clock.

A sleep either wastes time on a fast machine or loses the race on a slow one (the gate runs on a laptop at load average 129 some days).
Wait on what you need (an `Event`, a poll of the state with a deadline, a fake clock), or hold a process or task open with a sleep
that a test kills or cancels. Each row is a file that sleeps today: `kept` rows hold a child or a task open until the test stops it;
`debt` rows wait by the clock and are owed a conversion. A new sleep never joins; a file that sleeps less shrinks its row; a file that no
longer sleeps loses it. `sleep(0)` (a yield) is not a sleep. The sleeps inside a string run in a child process and are not seen.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

from any_arch import Rule, check, plant, rows

if TYPE_CHECKING:
    from collections.abc import Iterator

    from any_arch import Hit, Source

_ROOT = Path(__file__).resolve().parent.parent
_MODULES = {"time", "asyncio", "anyio"}
_SCOPE = ("packages/*/tests/**/*.py", "tests/**/*.py")


def _from_sleep(tree: ast.AST) -> set[str]:
    """Names bound by ``from time|asyncio|anyio import sleep [as x]``, as the file spells them."""
    return {
        a.asname or a.name
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and n.module in _MODULES
        for a in n.names
        if a.name == "sleep"
    }


def _sleeps(source: Source) -> Iterator[Hit]:
    bare = _from_sleep(source.tree)
    for node in ast.walk(source.tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        dotted = isinstance(fn, ast.Attribute) and fn.attr == "sleep" and isinstance(fn.value, ast.Name) and fn.value.id in _MODULES
        if not (dotted or (isinstance(fn, ast.Name) and fn.id in bare)):
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == 0:
            continue
        yield source.rel, node.lineno


_ALLOWED = {
    **rows(
        "kept: holds a child process or a task open for a long time until the test kills or cancels it",
        ("packages/any-json-doc/tests/test_doc.py", 1),
        ("packages/any-pipeline/tests/test_pipeline_runs.py", 4),
        ("packages/any-speech/tests/test_speech_adapters.py", 2),
        ("packages/any-supervise/tests/_worker.py", 1),
        ("packages/anyllm/tests/test_codex_process.py", 1),
        ("packages/async-scope/tests/test_asgi.py", 2),
        ("packages/async-scope/tests/test_cleanup.py", 5),
        ("packages/stream-proc/tests/test_capture.py", 1),
        ("packages/stream-proc/tests/test_detach.py", 1),
        ("packages/stream-proc/tests/test_procmac.py", 1),
        ("packages/stream-proc/tests/test_pump.py", 1),
        ("packages/stream-proc/tests/test_stop_report.py", 2),
        ("packages/stream-proc/tests/test_stop_shell_wait.py", 1),
    ),
    **rows(
        "debt: waits by the clock; wait on an Event, a state poll with a deadline, or a fake clock instead",
        ("packages/any-agent/tests/test_supervisor.py", 2),
        ("packages/any-browser/tests/test_playwright_backend.py", 7),
        ("packages/any-browser/tests/test_zendriver_backend.py", 1),
        ("packages/any-lease/tests/test_lease_processes.py", 2),
        ("packages/any-lease/tests/test_leases.py", 3),
        ("packages/any-lease/tests/test_run_cli.py", 1),
        ("packages/any-speech/tests/test_drain.py", 2),
        ("packages/any-supervise/tests/test_fleet.py", 1),
        ("packages/async-scope/tests/test_async_scope.py", 1),
        ("packages/async-scope/tests/test_property_async_scope.py", 1),
        ("packages/async-scope/tests/test_spawn.py", 2),
        ("packages/async-scope/tests/test_to_thread_joined.py", 3),
        ("packages/git-porcelain/tests/test_real_read_timeout.py", 2),
        ("packages/jsonl-log/tests/test_rotate_lock.py", 1),
        ("packages/mcp-bridge/tests/test_mcp_bridge.py", 2),
        ("packages/process-lock/tests/test_lock_features.py", 1),
    ),
}

SLEEPS = Rule(
    "sleep-in-tests",
    "wait for the event or condition, not the clock; a converted file: shrink its row",
    _sleeps,
    _ALLOWED,
    kinds=("kept", "debt"),
    scope=_SCOPE,
)


def test_tests_do_not_sleep_beyond_the_rows_that_list_them() -> None:
    check(SLEEPS, _ROOT)


def test_a_planted_sleep_is_seen_and_a_yield_is_not(tmp_path: Path) -> None:
    code = (
        "import time\nimport asyncio\nfrom time import sleep as nap\ntime.sleep(1)\nnap(2)\n"
        "async def f():\n    await asyncio.sleep(0)\n    await asyncio.sleep(0.1)\n"
    )
    assert plant(SLEEPS, tmp_path, code, "packages/pkg/tests/test_x.py") == {"packages/pkg/tests/test_x.py": [4, 5, 8]}
