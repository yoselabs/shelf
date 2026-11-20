"""One owner for binary discovery and for the environment a child gets (shelf-tyld.5).

Two static rules over every ``packages/*/src`` module:

- ``shutil.which`` (called, or referenced as a default such as ``which=shutil.which``) lives only in child-env's
  ``exe.py``; everyone else calls ``child_env.find``, whose PATH is the injected env and which raises on a miss.
- A whole process environment is never handed to a child: ``env=os.environ``, ``env=dict(os.environ)``,
  ``env={**os.environ, ...}``, ``env=os.environ.copy()`` on any call. Build the child's env with ``child_env.build_env``.

Both allowlists name the CURRENT callers only, each a debt. The consumer wave (shelf-tyld.5 follow-ups) empties
them; an entry that no longer offends fails the test, so a fixed caller must be removed from the list.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

_ROOT = Path(__file__).resolve().parent.parent
_SRC = sorted((_ROOT / "packages").glob("*/src/**/*.py"))

_OWNER = "packages/child-env/src/child_env/exe.py"

# CURRENT callers of shutil.which. The consumer wave empties this.
_WHICH_ALLOWED = {
    "packages/blueprint/src/blueprint/concerns/stack.py",
    "packages/blueprint/src/blueprint/model.py",
    "packages/blueprint/src/blueprint/init.py",  # stdlib-only engine: looks on the injected env's PATH
}

# CURRENT callers that pass a whole os.environ as a child's env. The consumer wave empties this. Only a literal
# env=<whole environ> keyword is seen: blueprint's gate_state.py and testing.py build the dict in a variable first
# (the consumer wave routes those through build_env too; this test does not follow data flow).
_WHOLE_ENV_ALLOWED: set[str] = {
    # the gate passes the caller's own environment to the recipes and pytest it launches (UV_*, MISE_*, GIT_*, PRE_COMMIT_*)
    # the edge hands `blueprint init` the user's environment: prek, mise and bd it launches need PATH, HOME and their own settings
    # `python -m any_lease run` is a lock around a command: it must behave as running the command directly, whole environment included
    "packages/any-lease/src/any_lease/__main__.py",
    "packages/blueprint/src/blueprint/__main__.py",
    "packages/any-gate/src/any_gate/cli.py",
    "packages/any-gate-python/src/any_gate_python/cli.py",
}


def _rel(path: Path) -> str:
    return path.relative_to(_ROOT).as_posix()


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


def _uses_which(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "which" and isinstance(node.value, ast.Name) and node.value.id == "shutil":
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "shutil" and any(a.name == "which" for a in node.names):
            return True
    return False


def _passes_whole_environ(tree: ast.AST) -> bool:
    return any(
        isinstance(n, ast.Call) and any(kw.arg == "env" and _is_whole_environ(kw.value) for kw in n.keywords) for n in ast.walk(tree)
    )


def _offenders(check: Callable[[ast.AST], bool]) -> set[str]:
    return {_rel(p) for p in _SRC if check(ast.parse(p.read_text(encoding="utf-8")))}


def test_shutil_which_lives_only_in_the_owner() -> None:
    found = _offenders(_uses_which)
    assert found - {_OWNER} - _WHICH_ALLOWED == set(), "use child_env.find(name, env, extra_dirs) instead of shutil.which"


def test_the_which_allowlist_names_only_current_callers() -> None:
    assert _WHICH_ALLOWED - _offenders(_uses_which) == set(), "fixed caller: remove it from _WHICH_ALLOWED"


def test_no_child_gets_a_whole_process_environment() -> None:
    found = _offenders(_passes_whole_environ)
    assert found - _WHOLE_ENV_ALLOWED == set(), "build the child's env with child_env.build_env, never env=os.environ"


def test_the_whole_env_allowlist_names_only_current_callers() -> None:
    assert _WHOLE_ENV_ALLOWED - _offenders(_passes_whole_environ) == set(), "fixed caller: remove it from _WHOLE_ENV_ALLOWED"


def test_the_detector_sees_every_whole_environment_shape() -> None:
    for src in ("f(env=os.environ)", "f(env=dict(os.environ))", "f(env={**os.environ, 'A': '1'})", "f(env=os.environ.copy())"):
        assert _passes_whole_environ(ast.parse(src)), src
    for src in ("f(env=build_env(e))", "f(env={'A': '1'})", "f(env=dict(e))", "f(cwd=os.environ)"):
        assert not _passes_whole_environ(ast.parse(src)), src


def test_the_detector_sees_every_which_shape() -> None:
    for src in ("shutil.which('x')", "def f(which=shutil.which): ...", "from shutil import which"):
        assert _uses_which(ast.parse(src)), src
    assert not _uses_which(ast.parse("find('x', env)"))
