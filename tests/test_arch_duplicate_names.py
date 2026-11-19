"""One name, one contract: a Protocol's name is not reused by another package (bead shelf-tyld.9).

Two packages that each define `Embedder` or `Run` make `from x import Run` a guess and an
IDE jump a coin toss, and invite a merge of two different contracts. Found by AST scan on
2026-11-20: any-speech `Embedder` (a voice) beside anyembed `Embedder` (text), and any-speech
`Run` (a command runner) beside any-pipeline `Run` (a stage's run); both renamed in any-speech.

What it checks: a public (no leading underscore) class in `packages/*/src` that is a Protocol
must not share its name with a class of any kind in another package. What it does not check:
duplicates between two non-Protocol classes (dataclasses such as `Verdict` or `Finding`),
which carry no cross-package contract. Nested classes are scanned like top-level ones.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# Protocol name -> why the clash with another package's class stays.
_ALLOWED: dict[str, str] = {
    "Outcome": (
        "a2effect's Outcome is the effect result protocol; any-agent and any-proc `Outcome` are their own result records, "
        "and neither imports a2effect"
    ),
    "Repo": (
        "git-porcelain's Repo is the public repository protocol; blueprint's Repo is a test helper "
        "(blueprint/testing.py) wrapping a throwaway git repo"
    ),
    "Run": (
        "any-pipeline's Run is what a stage needs from its run; blueprint's Run is the engine's result record, "
        "and blueprint does not import any-pipeline"
    ),
    "Store": (
        "any-pipeline's Store is the stage cache protocol; git-porcelain's is its in-memory fake object store "
        "and sqlite-store's is a table store; none imports another"
    ),
}


def _classes(source: str) -> list[tuple[str, bool]]:
    """(name, is_protocol) for each top-level-or-nested public class in ``source``."""
    found: list[tuple[str, bool]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            is_protocol = any(ast.unparse(base).split("[")[0].split(".")[-1] == "Protocol" for base in node.bases)
            found.append((node.name, is_protocol))
    return found


def _clashes(sources: dict[str, str]) -> dict[str, list[str]]:
    """Protocol names that another package's class also carries -> the packages involved."""
    owners: dict[str, set[str]] = defaultdict(set)
    protocols: set[str] = set()
    for package, source in sources.items():
        for name, is_protocol in _classes(source):
            owners[name].add(package)
            if is_protocol:
                protocols.add(name)
    return {name: sorted(owners[name]) for name in sorted(protocols) if len(owners[name]) > 1}


def _shelf_sources() -> dict[str, str]:
    sources: dict[str, list[str]] = defaultdict(list)
    for path in (_ROOT / "packages").glob("*/src/**/*.py"):
        sources[path.relative_to(_ROOT / "packages").parts[0]].append(path.read_text(encoding="utf-8"))
    return {package: "\n".join(texts) for package, texts in sources.items()}


def test_no_protocol_name_is_shared_across_packages_except_the_allowed() -> None:
    sources = _shelf_sources()
    assert sources, "no package sources found; the walk is vacuous"
    clashes = _clashes(sources)
    new = {name: pkgs for name, pkgs in clashes.items() if name not in _ALLOWED}
    assert not new, "Protocol name reused in another package; rename one (they are different things) or merge:\n  " + "\n  ".join(
        f"{name}: {pkgs}" for name, pkgs in new.items()
    )
    stale = sorted(set(_ALLOWED) - set(clashes))
    assert not stale, f"allowlist entries that no longer clash; delete them: {stale}"


def test_the_rule_flags_a_protocol_beside_a_class_of_the_same_name() -> None:
    sources = {
        "a": "from typing import Protocol\nclass Run(Protocol):\n    ...\nclass Gen[T](Protocol):\n    ...\n",
        "b": "class Run:\n    ...\nclass _Gen:\n    ...\nclass Plain:\n    ...\n",
        "c": "class Plain:\n    ...\nclass Gen:\n    ...\n",
    }
    assert _clashes(sources) == {"Gen": ["a", "c"], "Run": ["a", "b"]}
