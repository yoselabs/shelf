"""One owner for spawning, killing and liveness (constitution Article III, bead shelf-tyld.1).

The target rule, checked statically over every ``packages/*/src`` and ``tools`` file (tests excluded; ruff TID251 covers
those):

- ``os.killpg(...)``, ``start_new_session=True`` and ``os.kill(x, 0)`` appear only in stream-proc;
- a ``subprocess`` run or spawn (``run``, ``Popen``, ``call``, ``check_call``, ``check_output``) carries a ``timeout=``,
  except in stream-proc, any-proc and git-porcelain.

Each rule's rows are the files that break it TODAY. A file leaves them when the consumer wave moves it onto
stream-proc; a new file can never join, and a listed file that no longer breaks the rule fails the test (shrink the list).
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
_OWNER = "packages/stream-proc/"
_SPAWNERS = ("packages/stream-proc/", "packages/any-proc/", "packages/git-porcelain/")
_SPAWN_CALLS = {"run", "Popen", "call", "check_call", "check_output"}
_SCOPE = ("packages/*/src/**/*.py", "tools/**/*.py")

# to be emptied by the consumer wave: files that kill, signal-0 probe or session-spawn themselves today
_KILL_ALLOWED = {
    **rows("debt: session spawn only: wait4 alone gives ru_maxrss", "packages/any-speech/src/any_speech/adapters/_child.py"),
    **rows(
        "debt: SIGKILL of a worker group by pgid, no Popen in hand (stop_tree needs one)",
        "packages/anyllm/src/anyllm/providers/_agent.py",
    ),
}

# to be emptied by the consumer wave: files outside the spawners that run a subprocess with no timeout=
_UNBOUNDED_ALLOWED = {
    **rows(
        "kept: Popen runs up to four audits at once, each read through communicate(timeout=RUN_TIMEOUT) and killed on expiry; "
        "Popen itself has no timeout argument",
        "tools/corpus_diff.py",
    ),
    **rows(
        "kept: the run wrapper waits on an arbitrary user command, a deadline would kill it",
        "packages/any-lease/src/any_lease/__main__.py",
    ),
    **rows("kept: runs the repo's whole test suite, which has no fixed duration", "packages/blueprint/src/blueprint/gate_test.py"),
    **rows(
        "kept: recipes may run long (budgets only warn), get pass_fds; stream-proc.run lacks both",
        "packages/any-gate/src/any_gate/steps.py",
    ),
}


def _is(node: ast.expr, module: str, names: set[str]) -> bool:
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == module and node.attr in names


def _from_imports(tree: ast.AST, module: str) -> set[str]:
    """Names this file binds with ``from <module> import ...``, as the file spells them (so ``from os import killpg as k`` is seen)."""
    return {a.asname or a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == module for a in n.names}


def _kills(source: Source) -> Iterator[Hit]:
    if source.rel.startswith(_OWNER):
        return
    bare_killpg = _from_imports(source.tree, "os") & {"killpg"}
    for node in ast.walk(source.tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if _is(fn, "os", {"killpg"}) or (isinstance(fn, ast.Name) and fn.id in bare_killpg):
            yield source.rel, node.lineno
        if _is(fn, "os", {"kill"}) and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and node.args[1].value == 0:
            yield source.rel, node.lineno
        for kw in node.keywords:
            if kw.arg == "start_new_session" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                yield source.rel, node.lineno


def _unbounded(source: Source) -> Iterator[Hit]:
    if source.rel.startswith(_SPAWNERS):
        return
    bare = _from_imports(source.tree, "subprocess") & _SPAWN_CALLS
    for node in ast.walk(source.tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        spawns = _is(fn, "subprocess", _SPAWN_CALLS) or (isinstance(fn, ast.Name) and fn.id in bare)
        if spawns and not any(kw.arg == "timeout" for kw in node.keywords):
            yield source.rel, node.lineno


KILLS = Rule(
    "kill-and-session",
    "signal and session spawn belong to stream-proc (stop_tree, run, alive); a moved file: delete its row",
    _kills,
    _KILL_ALLOWED,
    scope=_SCOPE,
)
UNBOUNDED = Rule(
    "unbounded-subprocess",
    "give it timeout= or run it through stream_proc.capture/any_proc.call; a bounded file: delete its row",
    _unbounded,
    _UNBOUNDED_ALLOWED,
    scope=_SCOPE,
)


def test_kill_and_session_and_liveness_probe_live_only_in_stream_proc() -> None:
    check(KILLS, _ROOT)


def test_a_subprocess_outside_the_spawners_has_a_timeout() -> None:
    check(UNBOUNDED, _ROOT)


@pytest.mark.parametrize(
    ("source", "kill", "unbounded"),
    [
        ("import os\nos.killpg(1, 9)", 1, 0),
        ("from os import killpg\nkillpg(1, 9)", 1, 0),
        ("import os\nos.kill(5, 0)", 1, 0),
        ("import os\nos.kill(5, 9)", 0, 0),
        ("import subprocess\nsubprocess.Popen(['x'], start_new_session=True)", 1, 1),
        ("import subprocess\nsubprocess.Popen(['x'], start_new_session=flag)", 0, 1),
        ("import subprocess\nsubprocess.run(['x'], timeout=5)", 0, 0),
        ("import subprocess\nsubprocess.run(['x'])", 0, 1),
        ("from subprocess import run\nrun(['x'])", 0, 1),
    ],
)
def test_the_scanner_sees_what_it_claims_to(tmp_path: Path, source: str, kill: int, unbounded: int) -> None:
    def count(rule: Rule, name: str) -> int:
        return sum(len(lines) for lines in plant(rule, tmp_path / name, source).values())

    assert (count(KILLS, "kill"), count(UNBOUNDED, "unbounded")) == (kill, unbounded)


def test_the_owners_are_not_scanned(tmp_path: Path) -> None:
    source = "import os, subprocess\nos.killpg(1, 9)\nsubprocess.run(['x'])\n"
    assert plant(KILLS, tmp_path / "a", source, "packages/stream-proc/src/stream_proc/mod.py") == {}
    assert plant(UNBOUNDED, tmp_path / "b", source, "packages/any-proc/src/any_proc/mod.py") == {}
