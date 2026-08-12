"""The `linter-preset` operation — python+uv only (D2's stack tag).

Implements `docs/linting.md`'s own copy list, mechanically:

1. The `[tool.ruff]`, `[tool.ruff.lint]` (+ subtables), `[tool.codespell]`,
   `[tool.coverage.*]` blocks from shelf's `pyproject.toml`.
2. The `Makefile` targets (`check guard bootstrap bootstrap-verify lint format typecheck spell deps test`).
3. The `dev` dependency-group.

Resolution 0004 — "linters are a config-preset, not a CLI" — means this is a
**one-shot scaffold**, not a syncing tool: copy, then the consumer owns it.
That is also why the merge granularity is per-table / per-target, never
per-line: **a repo that already has its own `[tool.ruff]` keeps it exactly as
written** — this operation appends only what is genuinely absent, and never
opens an existing table to negotiate with its contents. `docs/linting.md`
itself says "own it" — line-level reconciliation is the consumer's judgment,
not this operation's to make.

Effect-assertion: after writing, `pyproject.toml` is re-parsed with `tomllib`
(catches injected syntax errors — a byte count matching is not proof the file
is still valid TOML), and each Makefile target name copied is confirmed
present as a `name:` line.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .operations import Outcome, Result

_SHELF_ROOT = Path(__file__).resolve().parent.parent.parent
_SHELF_PYPROJECT = _SHELF_ROOT / "pyproject.toml"
_SHELF_MAKEFILE = _SHELF_ROOT / "Makefile"

_TABLE_PREFIXES = ("tool.ruff", "tool.codespell", "tool.coverage")
_DEV_GROUP_TABLE = "dependency-groups"
_MAKE_TARGETS = ("check", "guard", "bootstrap", "bootstrap-verify", "lint", "format", "typecheck", "spell", "deps", "test")

_TOML_HEADER_RE = re.compile(r"^\[([^\]]+)\]\s*$", re.MULTILINE)
_MAKE_TARGET_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_.-]*):", re.MULTILINE)


def _split_toml_tables(text: str) -> list[tuple[str, str]]:
    """Top-level `[name]` tables, in file order, as `(name, block_text_incl_header)`."""
    matches = list(_TOML_HEADER_RE.finditer(text))
    return [(m.group(1), text[m.start() : (matches[i + 1].start() if i + 1 < len(matches) else len(text))]) for i, m in enumerate(matches)]


def _split_make_targets(text: str) -> list[tuple[str, str]]:
    """Top-level `name:` recipes, in file order, as `(name, block_text_incl_header)`."""
    matches = list(_MAKE_TARGET_RE.finditer(text))
    return [(m.group(1), text[m.start() : (matches[i + 1].start() if i + 1 < len(matches) else len(text))]) for i, m in enumerate(matches)]


def _owns(target_names: set[str], prefix: str) -> bool:
    """Whether the target already defines ANY table in `prefix`'s family (itself or a subtable).

    A consumer that already has `[tool.ruff]` (even with just one overridden key)
    has taken ownership of the whole ruff namespace — copying `[tool.ruff.lint]`
    alongside their own `[tool.ruff]` would silently graft shelf's rule set onto
    a table the consumer is deliberately diverging from. So ownership is
    per-family, not per-exact-table-name.
    """
    return any(name == prefix or name.startswith(prefix + ".") for name in target_names)


def _missing_toml_blocks(target_text: str) -> str:
    shelf_tables = _split_toml_tables(_SHELF_PYPROJECT.read_text())
    target_names = {name for name, _ in _split_toml_tables(target_text)}
    owned_prefixes = [prefix for prefix in _TABLE_PREFIXES if _owns(target_names, prefix)]

    blocks = [
        block
        for name, block in shelf_tables
        if name.startswith(_TABLE_PREFIXES) and not any(name == p or name.startswith(p + ".") for p in owned_prefixes)
    ]
    if _DEV_GROUP_TABLE not in target_names:
        blocks += [block for name, block in shelf_tables if name == _DEV_GROUP_TABLE]
    return "".join(blocks)


def _missing_make_blocks(target_text: str) -> str:
    shelf_targets = dict(_split_make_targets(_SHELF_MAKEFILE.read_text()))
    target_names = {name for name, _ in _split_make_targets(target_text)}
    return "".join(shelf_targets[name] for name in _MAKE_TARGETS if name in shelf_targets and name not in target_names)


@dataclass
class LinterPresetOperation:
    """Copies missing `pyproject.toml` tables and `Makefile` targets from shelf into `repo` (python+uv only)."""

    repo: Path
    name: str = "linter-preset"
    requires: tuple[str, ...] = ()

    def run(self, _results: dict[str, Result]) -> Result:
        """Copy every shelf table/target family not already owned by `repo`."""
        pyproject = self.repo / "pyproject.toml"
        if not pyproject.exists():
            return Result(Outcome.COULD_NOT_APPLY, verified=False, message=f"{pyproject} does not exist — not a python+uv target")

        applied: list[str] = []

        toml_text = pyproject.read_text()
        missing_toml = _missing_toml_blocks(toml_text)
        if missing_toml:
            new_toml = toml_text.rstrip("\n") + "\n\n" + missing_toml
            try:
                tomllib.loads(new_toml)
            except tomllib.TOMLDecodeError as exc:
                return Result(Outcome.FAILED, verified=False, message=f"copying the preset would break {pyproject}: {exc}")
            pyproject.write_text(new_toml)
            applied.append("pyproject.toml tables")

        makefile = self.repo / "Makefile"
        existing_make = makefile.read_text() if makefile.exists() else ""
        missing_make = _missing_make_blocks(existing_make)
        if missing_make:
            new_make = (existing_make.rstrip("\n") + "\n\n" if existing_make else "") + missing_make
            makefile.write_text(new_make)
            applied.append("Makefile targets")

        if not applied:
            return Result(Outcome.APPLIED, verified=True, message="already current — nothing to copy")

        try:
            tomllib.loads(pyproject.read_text())
        except tomllib.TOMLDecodeError as exc:
            return Result(Outcome.FAILED, verified=False, message=f"{pyproject} is not valid TOML after writing: {exc}")

        written_make_names = {name for name, _ in _split_make_targets(makefile.read_text())} if makefile.exists() else set()
        expected_names = {name for name in _MAKE_TARGETS if name in dict(_split_make_targets(_SHELF_MAKEFILE.read_text()))}
        missing_after = expected_names - written_make_names
        if missing_after:
            return Result(Outcome.FAILED, verified=False, message=f"Makefile still missing targets after write: {missing_after}")

        return Result(Outcome.APPLIED, verified=True, message=f"copied {', '.join(applied)}")
