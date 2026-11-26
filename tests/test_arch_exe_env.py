"""One owner for binary discovery and for the environment a child gets (shelf-tyld.5).

Two static rules over every ``packages/*/src`` module:

- ``shutil.which`` (called, or referenced as a default such as ``which=shutil.which``) lives only in child-env's
  ``exe.py``; everyone else calls ``child_env.find``, whose PATH is the injected env and which raises on a miss.
- A whole process environment is never handed to a child: ``env=os.environ``, ``env=dict(os.environ)``,
  ``env={**os.environ, ...}``, ``env=os.environ.copy()`` on any call. Build the child's env with ``child_env.build_env``.

Both sets of rows name the CURRENT callers only, each a debt. The consumer wave (shelf-tyld.5 follow-ups) empties
them; a row that no longer offends fails the test, so a fixed caller must be removed from the list. Only a literal
env=<whole environ> keyword is seen: blueprint's gate_state.py and testing.py build the dict in a variable first
(the consumer wave routes those through build_env too; this test does not follow data flow).
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from any_arch import Rule, check, plant, rows

from tests.arch_keys import DEBT_UNTIL

if TYPE_CHECKING:
    from collections.abc import Iterator

    from any_arch import Hit, Source

_ROOT = Path(__file__).resolve().parent.parent

_OWNER = "packages/child-env/src/child_env/exe.py"

_WHICH_DEBT = "debt: a current caller of shutil.which; the consumer wave moves it onto child_env.find"
_WHICH_ALLOWED = {
    **rows(_WHICH_DEBT, "packages/blueprint/src/blueprint/concerns/stacks/stack.py", "packages/blueprint/src/blueprint/model.py"),
    **rows("debt: stdlib-only engine: looks on the injected env's PATH", "packages/blueprint/src/blueprint/init.py"),
}

_WHOLE_ENV_ALLOWED = {
    # the gate passes the caller's own environment to the recipes and pytest it launches (UV_*, MISE_*, GIT_*, PRE_COMMIT_*)
    **rows(
        "debt: the gate passes the caller's own environment to the recipes and pytest it launches (UV_*, MISE_*, GIT_*, PRE_COMMIT_*)",
        "packages/any-gate/src/any_gate/cli.py",
        "packages/any-gate-python/src/any_gate_python/cli.py",
    ),
    **rows(
        "debt: the edge hands `blueprint init` the user's environment: "
        "prek, mise and bd it launches need PATH, HOME and their own settings",
        "packages/blueprint/src/blueprint/__main__.py",
    ),
    **rows(
        "debt: `python -m any_lease run` is a lock around a command: "
        "it must behave as running the command directly, whole environment included",
        "packages/any-lease/src/any_lease/__main__.py",
    ),
}


def _is_os_environ(node: ast.expr) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "environ" and isinstance(node.value, ast.Name) and node.value.id == "os"


def _is_whole_environ(node: ast.expr) -> bool:
    """``os.environ``, ``dict(os.environ)``, ``os.environ.copy()`` or a dict display that spreads ``os.environ``."""
    if _is_os_environ(node):
        return True
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id == "dict":
            return any(_is_whole_environ(a) for a in node.args)
        if isinstance(func, ast.Attribute) and func.attr == "copy":
            return _is_os_environ(func.value)
    if isinstance(node, ast.Dict):
        return any(k is None and _is_whole_environ(v) for k, v in zip(node.keys, node.values, strict=True))
    return False


def _uses_which(source: Source) -> Iterator[Hit]:
    if source.rel == _OWNER:
        return
    for node in ast.walk(source.tree):
        if (
            isinstance(node, ast.Attribute) and node.attr == "which" and isinstance(node.value, ast.Name) and node.value.id == "shutil"
        ) or (isinstance(node, ast.ImportFrom) and node.module == "shutil" and any(a.name == "which" for a in node.names)):
            yield source.rel, node.lineno


def _passes_whole_environ(source: Source) -> Iterator[Hit]:
    for node in ast.walk(source.tree):
        if isinstance(node, ast.Call) and any(kw.arg == "env" and _is_whole_environ(kw.value) for kw in node.keywords):
            yield source.rel, node.lineno


WHICH = Rule(
    "shutil-which",
    "use child_env.find(name, env, extra_dirs) instead of shutil.which; a fixed caller: remove its row",
    _uses_which,
    _WHICH_ALLOWED,
    ("debt",),
    debt_until=DEBT_UNTIL,
)
WHOLE_ENV = Rule(
    "whole-environment",
    "build the child's env with child_env.build_env, never env=os.environ; a fixed caller: remove its row",
    _passes_whole_environ,
    _WHOLE_ENV_ALLOWED,
    ("debt",),
    debt_until=DEBT_UNTIL,
)


def test_shutil_which_lives_only_in_the_owner_and_the_rows_name_only_current_callers() -> None:
    check(WHICH, _ROOT)


def test_no_child_gets_a_whole_process_environment_and_the_rows_name_only_current_callers() -> None:
    check(WHOLE_ENV, _ROOT)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("f(env=os.environ)", True),
        ("f(env=dict(os.environ))", True),
        ("f(env={**os.environ, 'A': '1'})", True),
        ("f(env=os.environ.copy())", True),
        ("f(env=build_env(e))", False),
        ("f(env={'A': '1'})", False),
        ("f(env=dict(e))", False),
        ("f(cwd=os.environ)", False),
    ],
)
def test_the_detector_sees_every_whole_environment_shape(tmp_path: Path, source: str, expected: bool) -> None:
    assert bool(plant(WHOLE_ENV, tmp_path, source)) is expected, source


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("shutil.which('x')", True),
        ("def f(which=shutil.which): ...", True),
        ("from shutil import which", True),
        ("find('x', env)", False),
    ],
)
def test_the_detector_sees_every_which_shape(tmp_path: Path, source: str, expected: bool) -> None:
    assert bool(plant(WHICH, tmp_path, source)) is expected, source


def test_the_owner_may_use_which(tmp_path: Path) -> None:
    assert plant(WHICH, tmp_path, "import shutil\nshutil.which('x')\n", _OWNER) == {}
