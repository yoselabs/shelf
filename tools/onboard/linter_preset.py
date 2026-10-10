"""The `linter-preset` operation — python+uv only (D2's stack tag).

Implements `docs/linting.md`'s own copy list, mechanically:

1. The `[tool.ruff]`, `[tool.ruff.lint]` (+ subtables), `[tool.codespell]`,
   `[tool.coverage.*]` blocks from shelf's `pyproject.toml`.
2. The `Makefile` targets (`check guard preset bootstrap bootstrap-verify lint format typecheck spell deps test`);
   `check` is the plain gate (the shelf's own dispatches to its container), and `deps` is rewritten
   for a single-package repo, since the shelf's own loops over `packages/*`.
3. The `dev` dependency-group.
4. A `[tool.pyrefly]` and a `[tool.pytest.ini_options]` built for a consumer: the shelf's strict
   preset and error severities (the axis `make preset` compares), its lighter bar for tests, and
   none of the shelf's own include/exclude/search paths or testpaths.

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
is still valid TOML), and `make -n check` runs in the repo: every target the gate
names must resolve. Checking that target names were written was not enough —
shelf-4mz shipped a `check` that depended on a `preset` target never copied.
"""

from __future__ import annotations

import re
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .operations import Outcome, Result

_SHELF_ROOT = Path(__file__).resolve().parent.parent.parent
_SHELF_PYPROJECT = _SHELF_ROOT / "pyproject.toml"
_SHELF_MAKEFILE = _SHELF_ROOT / "Makefile"

_TABLE_PREFIXES = ("tool.ruff", "tool.codespell", "tool.coverage")
_DEV_GROUP_TABLE = "dependency-groups"
_MAKE_TARGETS = (
    "check",
    "guard",
    "preset",
    "bootstrap",
    "bootstrap-verify",
    "lint",
    "format",
    "typecheck",
    "spell",
    "deps",
    "test",
    "cov",
    "sync",
    "blueprint",
)

_GENERATED_PREFIXES = ("tool.pyrefly", "tool.pytest")
_SHELF_TESTS_SUBCONFIG = "packages/*/tests/**"
_CONSUMER_DEPS = """# dependency hygiene: unused, missing and transitive dependencies (deptry).
deps:
\tuv run deptry .

"""
# The shelf's `check` dispatches to a container and to targets a consumer is not given
# (check-host, test-affected); a consumer gets the plain gate.
_CONSUMER_CHECK = """# The gate. Fast, deterministic tools first; tests last.
check: guard preset blueprint lint typecheck spell deps test

"""
_CONSUMER_PYTEST = """[tool.pytest.ini_options]
addopts = "-ra --strict-markers"

"""

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


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _consumer_pyrefly() -> str:
    """The shelf's strict pyrefly for a consumer: preset, error severities, the lighter test bar."""
    shelf = tomllib.loads(_SHELF_PYPROJECT.read_text())["tool"]["pyrefly"]
    errors = "".join(f"{key} = {_toml_value(value)}\n" for key, value in shelf.get("errors", {}).items())
    no_subconfig: dict[str, Any] = {}
    tests = next((sub for sub in shelf.get("sub-config", []) if sub.get("matches") == _SHELF_TESTS_SUBCONFIG), no_subconfig)
    test_errors = "".join(f"{key} = {_toml_value(value)}\n" for key, value in tests.get("errors", {}).items())
    return (
        f"[tool.pyrefly]\npreset = {_toml_value(shelf['preset'])}\n\n[tool.pyrefly.errors]\n{errors}\n"
        f'[[tool.pyrefly.sub-config]]\nmatches = "tests/**"\n\n[tool.pyrefly.sub-config.errors]\n{test_errors}\n'
    )


def _missing_generated_blocks(target_text: str) -> str:
    target_names = {name for name, _ in _split_toml_tables(target_text)} | {
        m.group(1) for m in re.finditer(r"^\[\[([^\]]+)\]\]", target_text, re.MULTILINE)
    }
    blocks = []
    if not _owns(target_names, "tool.pyrefly"):
        blocks.append(_consumer_pyrefly())
    if not _owns(target_names, "tool.pytest"):
        blocks.append(_CONSUMER_PYTEST)
    return "".join(blocks)


def _gate_resolves(repo: Path) -> str | None:
    """`None` when every target `make check` names resolves; otherwise make's complaint."""
    try:
        dry = subprocess.run(["make", "-n", "check"], cwd=repo, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return "make is not installed -- cannot verify the copied gate"
    return None if dry.returncode == 0 else (dry.stderr.strip() or dry.stdout.strip())


def _make_targets_to_copy(target_text: str) -> list[str]:
    shelf_targets = dict(_split_make_targets(_SHELF_MAKEFILE.read_text()))
    target_names = {name for name, _ in _split_make_targets(target_text)}

    to_copy = [name for name in _MAKE_TARGETS if name in shelf_targets and name not in target_names]
    # `bootstrap-verify: bootstrap` is meaningless on its own: found against a real consumer
    # (a2kay) that already owned an unrelated `bootstrap:` target of its own (a very common
    # Make target name) -- `bootstrap` was correctly skipped as owned, but `bootstrap-verify`
    # was still copied, silently aliasing to the consumer's OWN unrelated target. If `bootstrap`
    # isn't ours to add (already present under any meaning), its dependent isn't either.
    if "bootstrap-verify" in to_copy and "bootstrap" in target_names and "bootstrap" not in to_copy:
        to_copy.remove("bootstrap-verify")

    return to_copy


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
        missing_toml = _missing_toml_blocks(toml_text) + _missing_generated_blocks(toml_text)
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
        to_copy = _make_targets_to_copy(existing_make)
        if to_copy:
            shelf_targets = dict(_split_make_targets(_SHELF_MAKEFILE.read_text()))
            shelf_targets["check"] = _CONSUMER_CHECK
            if not (self.repo / "packages").is_dir():
                shelf_targets["deps"] = _CONSUMER_DEPS
            new_make = (existing_make.rstrip("\n") + "\n\n" if existing_make else "") + "".join(shelf_targets[name] for name in to_copy)
            makefile.write_text(new_make)
            applied.append("Makefile targets")

        return _verify(self.repo, applied, to_copy)


def _verify(repo: Path, applied: list[str], to_copy: list[str]) -> Result:
    """Assert the effect: valid TOML, every copied target present, and `make check` resolving."""
    pyproject, makefile = repo / "pyproject.toml", repo / "Makefile"
    done = f"copied {', '.join(applied)}" if applied else "already current — nothing to copy"
    try:
        tomllib.loads(pyproject.read_text())
    except tomllib.TOMLDecodeError as exc:
        return Result(Outcome.FAILED, verified=False, message=f"{pyproject} is not valid TOML after writing: {exc}")
    written = {name for name, _ in _split_make_targets(makefile.read_text())} if makefile.exists() else set()
    if missing := set(to_copy) - written:
        return Result(Outcome.FAILED, verified=False, message=f"Makefile still missing targets after write: {missing}")
    if makefile.exists() and (complaint := _gate_resolves(repo)):
        return Result(Outcome.FAILED, verified=False, message=f"{done}, but make check does not resolve: {complaint}")
    return Result(Outcome.APPLIED, verified=True, message=done)
