"""A hand-made thread has a named owner (constitution Article III, bead shelf-tyld.8).

Checked statically over every ``packages/*/src`` and ``tools`` file (tests excluded; ruff TID251 covers those): a
``threading.Thread`` / ``threading.Timer`` / ``ThreadPoolExecutor`` construction appears only in a file listed below, each
with the reason a plain async stage cannot do the job. A new file never joins the list without a reason; a listed file
that no longer builds a thread fails the test (shrink the list). Locks, events and thread-locals are not threads and are
not checked.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

_ROOT = Path(__file__).resolve().parent.parent
_CONSTRUCTORS = {
    "threading": {"Thread", "Timer"},
    "concurrent.futures": {"ThreadPoolExecutor"},
    "concurrent.futures.thread": {"ThreadPoolExecutor"},
}

_ALLOWED = {
    "packages/stream-proc/src/stream_proc/pump.py": (
        "owner of child pipes: one reader thread per output pipe and a stdin feeder, released by the owner; sync API by design"
    ),
    "packages/any-gate/src/any_gate/steps.py": (
        "fan-out of blocking `just` recipes with pass_fds, one thread per step joined together; run_steps is sync by design"
    ),
    "packages/any-net/src/any_net/probe.py": (
        "blocking adapter: getaddrinfo ignores socket timeouts, so each probe is a daemon thread joined to one deadline; probe() is sync"
    ),
}


def _sources() -> list[Path]:
    return sorted([*_ROOT.glob("packages/*/src/**/*.py"), *_ROOT.glob("tools/**/*.py")])


def _findings(tree: ast.AST) -> list[str]:
    bare = {
        (a.asname or a.name)
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and n.module in _CONSTRUCTORS
        for a in n.names
        if a.name in _CONSTRUCTORS[n.module or ""]
    }
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        dotted = isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.attr in _CONSTRUCTORS.get(fn.value.id, set())
        if dotted or (isinstance(fn, ast.Name) and fn.id in bare):
            found.append(f"line {node.lineno}: a hand-made thread")
    return found


def _scan(check: Callable[[ast.AST], list[str]] = _findings) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for path in _sources():
        hits = check(ast.parse(path.read_text(encoding="utf-8")))
        if hits:
            out[path.relative_to(_ROOT).as_posix()] = hits
    return out


def test_a_thread_is_built_only_in_a_listed_file() -> None:
    new = {f: v for f, v in _scan().items() if f not in _ALLOWED}
    assert not new, f"use an any_pipeline.blocking stage or async_scope.to_thread_joined, or list the file with a reason: {new}"


def test_every_listed_file_still_builds_a_thread() -> None:
    stale = sorted(_ALLOWED.keys() - _scan().keys())
    assert not stale, f"these files build no thread now: delete them from _ALLOWED: {stale}"


def test_every_listed_file_has_a_reason() -> None:
    assert all(why.strip() for why in _ALLOWED.values())


@pytest.mark.parametrize(
    ("source", "count"),
    [
        ("import threading\nthreading.Thread(target=f)", 1),
        ("import threading\nthreading.Timer(1, f)", 1),
        ("from threading import Thread\nThread(target=f)", 1),
        ("from concurrent.futures import ThreadPoolExecutor as P\nP(2)", 1),
        ("import threading\nthreading.Lock()\nthreading.Event()", 0),
        ("import threading\nclass L(threading.local): ...", 0),
    ],
)
def test_the_scanner_sees_what_it_claims_to(source: str, count: int) -> None:
    assert len(_findings(ast.parse(source))) == count
