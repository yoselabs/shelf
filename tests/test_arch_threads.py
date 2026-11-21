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
from any_arch import Row, Rule, check, plant

if TYPE_CHECKING:
    from collections.abc import Iterator

    from any_arch import Hit, Source

_ROOT = Path(__file__).resolve().parent.parent
_CONSTRUCTORS = {
    "threading": {"Thread", "Timer"},
    "concurrent.futures": {"ThreadPoolExecutor"},
    "concurrent.futures.thread": {"ThreadPoolExecutor"},
}

_ALLOWED = {
    key: Row(reason)
    for key, reason in {
        "packages/stream-proc/src/stream_proc/pump.py": (
            "owner of child pipes: one reader thread per output pipe and a stdin feeder, released by the owner; sync API by design"
        ),
        "packages/any-gate/src/any_gate/steps.py": (
            "fan-out of blocking `just` recipes with pass_fds, one thread per step joined together; run_steps is sync by design"
        ),
        "packages/any-net/src/any_net/probe.py": (
            "blocking adapter: getaddrinfo ignores socket timeouts, so each probe is a daemon thread joined to one deadline; "
            "probe() is sync"
        ),
    }.items()
}


def _threads(source: Source) -> Iterator[Hit]:
    tree = source.tree
    bare = {
        (a.asname or a.name)
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and n.module in _CONSTRUCTORS
        for a in n.names
        if a.name in _CONSTRUCTORS[n.module or ""]
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        dotted = isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.attr in _CONSTRUCTORS.get(fn.value.id, set())
        if dotted or (isinstance(fn, ast.Name) and fn.id in bare):
            yield source.rel, node.lineno


THREADS = Rule(
    "hand-made-threads",
    "use an any_pipeline.blocking stage or async_scope.to_thread_joined, or list the file with a reason",
    _threads,
    _ALLOWED,
    scope=("packages/*/src/**/*.py", "tools/**/*.py"),
)


def test_a_thread_is_built_only_in_a_listed_file_and_every_listed_file_still_builds_one() -> None:
    check(THREADS, _ROOT)


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
def test_the_scanner_sees_what_it_claims_to(tmp_path: Path, source: str, count: int) -> None:
    assert sum(len(lines) for lines in plant(THREADS, tmp_path, source).values()) == count
