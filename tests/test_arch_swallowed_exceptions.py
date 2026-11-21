"""No silent failures (constitution Article III): a handler that does nothing, and `contextlib.suppress`, are named rows.

Checked statically over every `packages/*/src` file (tests excluded). A hit is

- an `except` handler whose whole body is `pass`, `...`, `continue`, a bare `return` or a docstring-like constant,
  with no raise and no log call, for any exception type (ruff BLE and TRY cover only part of `except Exception`), or
- a `with contextlib.suppress(...)` / `with suppress(...)`.

A handler that returns a value (`return None`, `return False`, `return []`) is NOT a hit: the value is the typed
answer the caller acts on (probing: file absent is a normal answer). Only silence is a hit.

Each file with hits is a row: `file -> (hit count, reason)`. The count is exact, so one more swallow in a listed file
fails the test, and a file whose hits are gone must be deleted from the list. Reason prefixes:

- `outcome:` the failure is the expected, named answer of this operation (absence, a torn or foreign line, a lost race,
  a probe that finds nothing); the function continues correctly and nothing is hidden from a caller
- `debt:` a real swallow still owed a conversion (let it raise, or report it); the reason names the fix
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent


def _silent(statement: ast.stmt) -> bool:
    if isinstance(statement, ast.Pass | ast.Continue):
        return True
    if isinstance(statement, ast.Expr):
        return isinstance(statement.value, ast.Constant)
    return isinstance(statement, ast.Return) and statement.value is None


def _suppresses(item: ast.withitem) -> bool:
    call = item.context_expr
    if not isinstance(call, ast.Call):
        return False
    func = call.func
    return (isinstance(func, ast.Name) and func.id == "suppress") or (
        isinstance(func, ast.Attribute) and func.attr == "suppress" and ast.unparse(func.value) == "contextlib"
    )


def swallowed(source: str) -> list[int]:
    """The line of each silent `except` handler and each `suppress(...)` in `source`."""
    lines: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ExceptHandler) and all(_silent(statement) for statement in node.body):
            lines.append(node.lineno)
        elif isinstance(node, ast.With | ast.AsyncWith):
            lines.extend(node.lineno for item in node.items if _suppresses(item))
    return sorted(lines)


def counts(root: Path) -> dict[str, int]:
    """`packages/<pkg>/src/...py` -> number of swallowed handlers, for the files that have any."""
    found: dict[str, int] = {}
    for path in sorted((root / "packages").glob("*/src/**/*.py")):
        hits = swallowed(path.read_text())
        if hits:
            found[path.relative_to(root).as_posix()] = len(hits)
    return found


def _rows(reason: str, *rows: tuple[str, int]) -> dict[str, tuple[int, str]]:
    return {f"packages/{path}": (count, reason) for path, count in rows}


_ALLOWED: dict[str, tuple[int, str]] = {
    # --- debt: real swallows, each with the fix ---
    **_rows(
        "debt: best-effort cleanup (context, page, browser, loop reader, fd) hides a failed close; report it through the "
        "engine's close result or let it raise after the engine is down",
        ("any-browser/src/any_browser/playwright.py", 14),
        ("any-browser/src/any_browser/zendriver.py", 4),
    ),
    **_rows(
        "debt: a failed best-effort write of the opencode session file is dropped; raise a typed error the caller can report",
        ("any-agent/src/any_agent/harnesses/opencode.py", 1),
    ),
    **_rows(
        "debt: a failed session DELETE on close is dropped; report it after the client closes",
        ("mcp-call/src/mcp_call/__init__.py", 1),
    ),
    **_rows(
        "debt: `except Exception: pass` (noqa BLE001) around a whole parse or encode; narrow to the parser's own error "
        "and fall back with a typed outcome",
        ("page-tsv/src/page_tsv/render.py", 1),
        ("content-extract/src/content_extract/__init__.py", 2),
    ),
    **_rows(
        "debt: a user callback (`cb`, `touch`) that raises is dropped so the pipe pump survives; report it as a typed "
        "callback failure on the run result",
        ("stream-proc/src/stream_proc/runner.py", 2),  # the second is a poll-slice timeout: an outcome
        ("stream-proc/src/stream_proc/pump.py", 7),
    ),
    **_rows(
        "debt: closing the sockets and the server's shutdown flag swallow `Exception`; narrow to OSError, let the rest raise",
        ("async-scope/src/async_scope/asgi.py", 3),
        ("async-scope/src/async_scope/__init__.py", 1),
    ),
    **_rows(
        "debt: a failed write of the probe cache row is dropped; the probe returns the answer, so the failure belongs in "
        "a logged warning or a typed outcome",
        ("any-net/src/any_net/probe.py", 1),
    ),
    # --- outcome: the failure is the expected answer ---
    **_rows(
        "outcome: a torn, foreign or undecodable line or item is skipped; the rest of the input is the answer",
        ("any-agent/src/any_agent/harnesses/codex.py", 2),
        ("any-agent/src/any_agent/harnesses/codex_rollout.py", 2),
        ("any-agent/src/any_agent/reset_parse.py", 2),
        ("any-breaker/src/any_breaker/ledger.py", 1),
        ("git-porcelain/src/git_porcelain/real_trace.py", 1),
        ("jsonl-log/src/jsonl_log/__init__.py", 5),
        ("jsonl-log/src/jsonl_log/cursor.py", 1),
        ("record-mine/src/record_mine/detector.py", 1),
    ),
    **_rows(
        "outcome: an absent, unreadable or vanished file or process is the normal answer of a probe, a scan or a race "
        "(the next candidate is tried, the slot is empty)",
        ("a2effect/src/a2effect/lint.py", 1),
        ("any-agent/src/any_agent/supervisor.py", 2),
        ("any-gate/src/any_gate/cli.py", 1),
        ("any-proc/src/any_proc/cpus.py", 2),
        ("any-proc/src/any_proc/run.py", 2),
        ("git-porcelain/src/git_porcelain/real_observe.py", 1),
        ("jsonl-log/src/jsonl_log/_retention.py", 1),
        ("jsonl-log/src/jsonl_log/_rewrite.py", 1),
        ("stream-proc/src/stream_proc/procfs.py", 1),
        ("stream-proc/src/stream_proc/procmac.py", 1),
        ("stream-proc/src/stream_proc/tree.py", 3),
    ),
    **_rows(
        "outcome: an optional lookup finds nothing, or a candidate fails to build, and the loop moves to the next one",
        ("any-gate-python/src/any_gate_python/select.py", 1),
        ("any-speech/src/any_speech/defaults.py", 1),
        ("anyllm/src/anyllm/select.py", 1),
        ("blueprint/src/blueprint/concerns/cli_parse.py", 1),
        ("convert-md/src/convert_md/dispatch.py", 1),
        ("launchd-agent/src/launchd_agent/__init__.py", 1),
    ),
    **_rows(
        "outcome: the loser of a race or a poll slice is the normal result: lock held by another worker, file already "
        "there, timeout slice elapsed, subscriber already gone, pipe closed by the exited child, process already dead",
        ("any-lease/src/any_lease/__main__.py", 1),
        ("any-lease/src/any_lease/leases.py", 1),
        ("any-speech/src/any_speech/drain.py", 1),
        ("anyllm/src/anyllm/providers/_agent.py", 1),
        ("event-bus/src/event_bus/__init__.py", 1),
        ("http-fetch/src/http_fetch/links.py", 1),
        ("sqlite-store/src/sqlite_store/connections.py", 1),
        ("sqlite-store/src/sqlite_store/store.py", 1),
        ("stream-proc/src/stream_proc/_exec_gate.py", 1),
        ("stream-proc/src/stream_proc/hold.py", 1),
        ("stream-proc/src/stream_proc/registered.py", 1),
    ),
}


def test_repo_has_no_unlisted_swallowed_exception() -> None:
    found = counts(_ROOT)
    over = {path: n for path, n in found.items() if n > _ALLOWED.get(path, (0, ""))[0]}
    assert not over, f"swallowed exceptions beyond their rows (let it raise, or return a typed outcome, or add a reasoned row): {over}"


def test_listed_files_still_swallow_exactly_that_many_and_carry_a_reason() -> None:
    found = counts(_ROOT)
    stale = {path: (count, found.get(path, 0)) for path, (count, _) in _ALLOWED.items() if found.get(path, 0) != count}
    assert not stale, f"rows out of date, (listed, found): {stale}"
    unreasoned = [path for path, (_, reason) in _ALLOWED.items() if not reason.startswith(("outcome: ", "debt: "))]
    assert not unreasoned, f"a row needs an `outcome:` or `debt:` reason: {unreasoned}"


@pytest.mark.parametrize(
    ("source", "count"),
    [
        ("try:\n    f()\nexcept OSError:\n    pass\n", 1),
        ("try:\n    f()\nexcept (OSError, ValueError):\n    ...\n", 1),
        ("for x in xs:\n    try:\n        f(x)\n    except KeyError:\n        continue\n", 1),
        ("def g():\n    try:\n        f()\n    except OSError:\n        return\n", 1),
        ("try:\n    f()\nexcept Exception:\n    pass\n", 1),
        ("with contextlib.suppress(KeyError):\n    f()\n", 1),
        ("with suppress(OSError, ValueError):\n    f()\n", 1),
        ("async def g():\n    async with suppress(OSError):\n        await f()\n", 1),
        ("try:\n    f()\nexcept OSError:\n    raise\n", 0),
        ("try:\n    f()\nexcept OSError as e:\n    log.warning('x', exc_info=e)\n", 0),
        ("try:\n    f()\nexcept OSError:\n    note()\n    pass\n", 0),
        ("def g():\n    try:\n        f()\n    except FileNotFoundError:\n        return None\n", 0),
        ("with open('x') as fh:\n    f(fh)\n", 0),
    ],
)
def test_the_scanner_sees_what_it_claims_to(source: str, count: int) -> None:
    assert len(swallowed(source)) == count


def test_a_planted_swallow_in_a_scratch_package_is_counted(tmp_path: Path) -> None:
    module = tmp_path / "packages" / "p" / "src" / "p" / "m.py"
    module.parent.mkdir(parents=True)
    module.write_text("try:\n    f()\nexcept OSError:\n    pass\n")
    assert counts(tmp_path) == {"packages/p/src/p/m.py": 1}
