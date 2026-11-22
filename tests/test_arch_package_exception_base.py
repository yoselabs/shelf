"""Package exception base (constitution Article III, "Two kinds of failure"): one root exception per package.

A caller who wants "anything this package refuses" writes one `except GitError`. That works only when every exception the
package defines derives, directly or through another of its own, from one class of that package. Two roots (a
`ValueError` subclass and a `RuntimeError` subclass side by side) mean the caller lists them all, and a new one added later
is caught by nobody.

An exception class is a class in `packages/*/src` with a base that is a builtin exception or an exception defined anywhere in the
shelf (resolved by simple name over the whole tree, to a fixpoint). A *root* is a package exception class none of whose
bases is another exception class of the same package. A package with more than one root is a hit: one row per package
(`packages/<name>`), one hit per root; the row's count is today's number of roots, so a new root fails.

Convention: the base is public and named `<Package>Error` (`AnyFileError`, `JsonlLogError`, `McpCallError`, `VerbCliError`); the
finder enforces only the single root, not the name. A package with one exception class is compliant as it is. Classes that stand in
for control flow and never reach a caller (`SystemExit` subclasses) still count: they are exceptions.

Limits: a base found by simple name can be another package's class of the same name (a collision makes a class look like an
exception and so can only add a root, never hide one); a class built by `type(...)` or a metaclass is not seen.

Rows: `packages/<name>` -> reason. `debt:` the package has several roots (fix: derive the others from the package base, or
fold them into it); `outcome:` the extra root is a deliberate separate hierarchy (a protocol signal that must not be caught by
`except PackageError`).
"""

from __future__ import annotations

import ast
import builtins
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from any_arch import Row, Rule, check, plant, rows
from any_arch.source import sources

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from any_arch import Hit, Source

_ROOT = Path(__file__).resolve().parent.parent
_SCOPE = ("packages/*/src/**/*.py",)
_BUILTIN_EXCEPTIONS = {n for n, v in vars(builtins).items() if isinstance(v, type) and issubclass(v, BaseException)}


def _bases(node: ast.ClassDef) -> list[str]:
    return [ast.unparse(base).split(".")[-1] for base in node.bases]


class _Packages:
    """package -> its root exception classes `(file, line, name)` and how many exception classes it defines."""

    def __init__(self, root: Path) -> None:
        classes = [(s.package, s.rel, n) for s in sources(root, _SCOPE) for n in ast.walk(s.tree) if isinstance(n, ast.ClassDef)]
        exceptions = set(_BUILTIN_EXCEPTIONS)
        grew = True
        while grew:
            grew = False
            for _, _, node in classes:
                if node.name not in exceptions and any(base in exceptions for base in _bases(node)):
                    exceptions.add(node.name)
                    grew = True
        defined: dict[str, set[str]] = {}
        for package, _, node in classes:
            if node.name in exceptions:
                defined.setdefault(package, set()).add(node.name)
        self.roots: dict[str, list[tuple[str, int, str]]] = {}
        for package, rel, node in classes:
            if node.name in defined.get(package, set()) and not any(base in defined[package] for base in _bases(node)):
                self.roots.setdefault(package, []).append((rel, node.lineno, node.name))


def _finder(root: Path) -> Callable[[Source], Iterable[Hit]]:
    built: list[_Packages] = []  # indexed on the first file seen, so a planted file is part of it

    def find(source: Source) -> Iterable[Hit]:
        if not built:
            built.append(_Packages(root))
        roots = built[0].roots.get(source.package, [])
        if len(roots) > 1:
            yield from ((f"packages/{source.package}", line) for rel, line, _ in roots if rel == source.rel)

    return find


_ALLOWED: dict[str, Row] = {
    **rows(
        "debt: `IntentNotRecordedError` (RuntimeError) beside the `EntrySignal` / `ParentGone` SystemExit signals; add `AnyAgentError` "
        "and derive the first from it (the signals may stay apart on purpose: `except AnyAgentError` must not stop a process exit)",
        ("packages/any-agent", 3),
    ),
    **rows(
        "debt: `FrontmatterError` (ValueError) and `StaleVersionError` (Exception) are separate roots; derive `StaleVersionError` "
        "from `FrontmatterError`",
        ("packages/any-frontmatter", 2),
    ),
    **rows(
        "debt: `ConflictError`, `RefusedError` and `ForeignVersionError` each derive from ValueError; add "
        "`AnyJsonDocError(ValueError)` as their base",
        ("packages/any-json-doc", 3),
    ),
    **rows(
        "debt: `LeaseTimeoutError` and `LeaseCancelledError` each derive from Exception; add `AnyLeaseError` as their base",
        ("packages/any-lease", 2),
    ),
    **rows(
        "debt: `FluidAudioError`, `EngineMissingError`, `MemoryBudgetError` and `SetupError` each derive from RuntimeError; add "
        "`AnySpeechError(RuntimeError)` as their base",
        ("packages/any-speech", 4),
    ),
    **rows(
        "debt: `AnyLLMError` exists but `CostViolation` (RuntimeError) and `_StartRefusedError` (Exception) bypass it; derive both "
        "from `AnyLLMError`",
        ("packages/anyllm", 3),
    ),
    **rows(
        "debt: `WobbleSkip` and `ParseError` each derive from Exception; add `LlmWobbleError` as their base",
        ("packages/llm-wobble", 2),
    ),
    **rows(
        "debt: `IdentityUnavailableError`, `RegisteredStartUncertainError` and `PumpStuckError` each derive from RuntimeError; add "
        "`StreamProcError(RuntimeError)` as their base",
        ("packages/stream-proc", 3),
    ),
}


def _rule(root: Path, allowed: dict[str, Row]) -> Rule:
    return Rule(
        "package-exception-base",
        "a package defines exceptions with more than one root (derive them from one package base class, or add a reasoned row)",
        _finder(root),
        allowed,
        ("debt", "outcome"),
        _SCOPE,
    )


PACKAGE_BASE = _rule(_ROOT, _ALLOWED)  # module level, so `python -m any_arch` finds its `debt:` rows


def test_repo_packages_have_one_exception_root_except_where_their_rows_list() -> None:
    check(PACKAGE_BASE, _ROOT)


_PLANTED = "class Base(Exception): ...\n"


@pytest.mark.parametrize(
    ("source", "lines"),
    [
        ("class A(ValueError): ...\nclass B(RuntimeError): ...\n", [1, 2]),
        ("class Base(Exception): ...\nclass Other(OSError): ...\nclass Child(Base): ...\n", [1, 2]),
        ("class Base(Exception): ...\nclass Mid(Base): ...\nclass Rogue(KeyError): ...\n", [1, 3]),
        ("import x\nclass A(Exception): ...\nclass B(x.Err): ...\nclass Err(Exception): ...\n", [2, 4]),
    ],
)
def test_a_planted_second_exception_root_is_found(tmp_path: Path, source: str, lines: list[int]) -> None:
    assert plant(_rule(tmp_path, {}), tmp_path, source) == {"packages/pkg": lines}


@pytest.mark.parametrize(
    "source",
    [
        "class A(ValueError): ...\n",
        "class Base(Exception): ...\nclass A(Base): ...\nclass B(A): ...\nclass C(Base, KeyError): ...\n",
        "class Base(Exception): ...\nclass Child(Base): ...\nclass Plain: ...\nclass Mixin(object): ...\n",
        "class Plain: ...\nclass Dataclass:\n    x: int = 1\n",
    ],
)
def test_one_root_or_no_exception_is_not_a_hit(tmp_path: Path, source: str) -> None:
    assert plant(_rule(tmp_path, {}), tmp_path, source) == {}


def test_a_root_is_found_through_another_package_exception(tmp_path: Path) -> None:
    plant(_rule(tmp_path, {}), tmp_path, "class LibError(Exception): ...\n", path="packages/lib/src/lib/__init__.py")
    app = "from lib import LibError\nclass AppError(LibError): ...\nclass Other(ValueError): ...\n"
    assert plant(_rule(tmp_path, {}), tmp_path, app, path="packages/app/src/app/__init__.py") == {"packages/app": [2, 3]}
