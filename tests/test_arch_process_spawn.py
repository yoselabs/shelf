"""One owner for spawning, killing and liveness (constitution Article III, bead shelf-tyld.1).

The target rule, checked statically over every ``packages/*/src`` and ``tools`` file (tests excluded; ruff TID251 covers
those):

- ``os.killpg(...)``, ``start_new_session=True`` and ``os.kill(x, 0)`` appear only in stream-proc;
- a ``subprocess`` run or spawn (``run``, ``Popen``, ``call``, ``check_call``, ``check_output``) carries a ``timeout=``,
  except in stream-proc, any-proc and git-porcelain.

Each allowlist below is the set of files that break the rule TODAY. A file leaves it when the consumer wave moves it onto
stream-proc; a new file can never join it, and a listed file that no longer breaks the rule fails the test (shrink the list).
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

_ROOT = Path(__file__).resolve().parent.parent
_OWNER = "packages/stream-proc/"
_SPAWNERS = ("packages/stream-proc/", "packages/any-proc/", "packages/git-porcelain/")
_SPAWN_CALLS = {"run", "Popen", "call", "check_call", "check_output"}

# to be emptied by the consumer wave: files that kill, signal-0 probe or session-spawn themselves today
_KILL_ALLOWLIST = {
    "packages/any-speech/src/any_speech/adapters/_child.py",  # session spawn only: wait4 alone gives ru_maxrss
}

# to be emptied by the consumer wave: files outside the spawners that run a subprocess with no timeout=
_UNBOUNDED_ALLOWLIST = {
    "packages/any-lease/src/any_lease/__main__.py",  # kept: the run wrapper waits on an arbitrary user command, a deadline would kill it
    "packages/blueprint/src/blueprint/gate_test.py",  # kept: runs the repo's whole test suite, which has no fixed duration
    "packages/blueprint/src/blueprint/recipes/check_dockerfile_pins.py",
    "packages/blueprint/src/blueprint/testing.py",
    "packages/shelf-vendor/src/shelf_vendor/__init__.py",
    "tools/affected.py",
    "tools/changed.py",
    "tools/gate_state.py",
    "tools/hooks/forbid-local-shelf-source.py",
    "tools/onboard/beads.py",
    "tools/onboard/hooks.py",
    "tools/onboard/linter_preset.py",
}


def _sources() -> list[Path]:
    return sorted([*_ROOT.glob("packages/*/src/**/*.py"), *_ROOT.glob("tools/**/*.py")])


def _rel(path: Path) -> str:
    return path.relative_to(_ROOT).as_posix()


def _is(node: ast.expr, module: str, names: set[str]) -> bool:
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == module and node.attr in names


def _from_imports(tree: ast.AST, module: str) -> set[str]:
    """Names this file binds with ``from <module> import ...``, as the file spells them (so ``from os import killpg as k`` is seen)."""
    return {a.asname or a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == module for a in n.names}


def _kill_findings(tree: ast.AST) -> list[str]:
    bare_killpg = _from_imports(tree, "os") & {"killpg"}
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if _is(fn, "os", {"killpg"}) or (isinstance(fn, ast.Name) and fn.id in bare_killpg):
            found.append(f"line {node.lineno}: os.killpg")
        if _is(fn, "os", {"kill"}) and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and node.args[1].value == 0:
            found.append(f"line {node.lineno}: os.kill(x, 0)")
        found += [
            f"line {node.lineno}: start_new_session=True"
            for kw in node.keywords
            if kw.arg == "start_new_session" and isinstance(kw.value, ast.Constant) and kw.value.value is True
        ]
    return found


def _unbounded_findings(tree: ast.AST) -> list[str]:
    bare = _from_imports(tree, "subprocess") & _SPAWN_CALLS
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        spawns = _is(fn, "subprocess", _SPAWN_CALLS) or (isinstance(fn, ast.Name) and fn.id in bare)
        if spawns and not any(kw.arg == "timeout" for kw in node.keywords):
            found.append(f"line {node.lineno}: subprocess call without timeout=")
    return found


def _scan(check: Callable[[ast.AST], list[str]], owners: tuple[str, ...]) -> dict[str, list[str]]:
    results: dict[str, list[str]] = {}
    for path in _sources():
        rel = _rel(path)
        if rel.startswith(owners):
            continue
        findings = check(ast.parse(path.read_text(encoding="utf-8")))
        if findings:
            results[rel] = findings
    return results


def test_kill_and_session_and_liveness_probe_live_only_in_stream_proc() -> None:
    found = _scan(_kill_findings, (_OWNER,))
    new = {f: v for f, v in found.items() if f not in _KILL_ALLOWLIST}
    assert not new, f"signal and session spawn belong to stream-proc (stop_tree, run, alive): {new}"


def test_the_kill_allowlist_lists_only_files_that_still_break_the_rule() -> None:
    found = _scan(_kill_findings, (_OWNER,))
    stale = sorted(_KILL_ALLOWLIST - found.keys())
    assert not stale, f"these files moved onto stream-proc: delete them from _KILL_ALLOWLIST: {stale}"


def test_a_subprocess_outside_the_spawners_has_a_timeout() -> None:
    found = _scan(_unbounded_findings, _SPAWNERS)
    new = {f: v for f, v in found.items() if f not in _UNBOUNDED_ALLOWLIST}
    assert not new, f"give it timeout= or run it through stream_proc.capture/any_proc.call: {new}"


def test_the_unbounded_allowlist_lists_only_files_that_still_break_the_rule() -> None:
    found = _scan(_unbounded_findings, _SPAWNERS)
    stale = sorted(_UNBOUNDED_ALLOWLIST - found.keys())
    assert not stale, f"these files are bounded now: delete them from _UNBOUNDED_ALLOWLIST: {stale}"


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
def test_the_scanner_sees_what_it_claims_to(source: str, kill: int, unbounded: int) -> None:
    tree = ast.parse(source)
    assert (len(_kill_findings(tree)), len(_unbounded_findings(tree))) == (kill, unbounded)
