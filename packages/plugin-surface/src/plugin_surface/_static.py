"""Describe a directory of plugin files without importing any of them.

:func:`load_surface` imports every module and calls every factory, so it can only
enumerate plugins you are already willing to run. An app that lets a user drop code
into a folder needs the step before that: *list* what is there so someone can decide
whether to trust it. That listing must not execute a line of the files it lists.

:func:`describe_directory` parses each file (``ast.parse``, never import) and returns
the value of one named module-level literal plus the names of the top-level
functions. Two rules, both learned from a consumer (a2kay's job directory):

- **Total per file.** Discovery is a whole-directory operation, so a file that
  raises hides every *other* file from the caller. Each problem — unreadable,
  unparsable, no declaration, a computed value — comes back as a
  :class:`Described` with ``problem`` set, never as an exception. One job file with
  an unusable value once made every job in its directory undiscoverable.
- **Every spelling the language allows.** ``NAME = {...}`` is an ``ast.Assign`` and
  ``NAME: dict[str, Any] = {...}`` is an ``ast.AnnAssign``. Matching only the first
  made adding a type annotation silently un-discover the plugin.

Only a pure literal is read (``ast.literal_eval``). A computed value is reported as
``not_literal`` rather than evaluated — evaluating it is exactly what this avoids.

What the literal *means* stays the consumer's: validate it with your own model, and
make that model total as well, for the same whole-directory reason.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pathlib import Path

Problem = Literal["unreadable", "unparsable", "missing", "not_literal", "not_mapping"]


@dataclass(frozen=True, slots=True)
class Described:
    """One plugin file, as far as reading its source can tell.

    ``declaration`` is the literal's value when ``problem`` is ``None``, else ``None``.
    ``detail`` carries the underlying error text for ``unreadable``/``unparsable``.
    ``functions`` is filled whenever the file parsed, so a consumer can check its
    entrypoint exists even when the declaration is missing.
    """

    path: Path
    declaration: dict[str, object] | None
    functions: frozenset[str]
    problem: Problem | None = None
    detail: str | None = None


def describe_directory(directory: Path, *, declaration: str, pattern: str = "*.py") -> list[Described]:
    """Describe every file matching ``pattern`` in ``directory``, sorted by path.

    ``declaration`` is the module-level name holding the plugin's metadata literal,
    e.g. ``"__myapp_plugin__"``. A missing directory is an empty list: no plugins is
    the normal state of a directory nobody has written to yet. Never raises per file.
    """
    if not directory.is_dir():
        return []
    return [describe_file(path, declaration=declaration) for path in sorted(directory.glob(pattern))]


def describe_file(path: Path, *, declaration: str) -> Described:
    """Describe one file. Never raises; see :class:`Described` for the outcomes."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return Described(path=path, declaration=None, functions=frozenset(), problem="unreadable", detail=str(exc))
    try:
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, ValueError) as exc:  # ValueError: a NUL byte in the source
        return Described(path=path, declaration=None, functions=frozenset(), problem="unparsable", detail=str(exc))

    functions = frozenset(node.name for node in tree.body if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef))
    value = _assigned_value(tree, declaration)
    if value is None:
        return Described(path=path, declaration=None, functions=functions, problem="missing")
    try:
        literal = ast.literal_eval(value)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return Described(path=path, declaration=None, functions=functions, problem="not_literal")
    if not isinstance(literal, dict):
        return Described(path=path, declaration=None, functions=functions, problem="not_mapping")
    return Described(path=path, declaration=literal, functions=functions)


def _assigned_value(tree: ast.Module, name: str) -> ast.expr | None:
    """The expression bound to ``name`` at module level, by either assignment form."""
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            return value
    return None


__all__ = ("Described", "Problem", "describe_directory", "describe_file")
