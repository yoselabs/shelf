"""The `linter-preset` operation — python+uv only (D2's stack tag).

Implements `docs/linting.md`'s own copy list, mechanically:

1. The `[tool.ruff]`, `[tool.ruff.lint]` (+ subtables), `[tool.codespell]`,
   `[tool.coverage.*]` and `[tool.shelf-size]` blocks from shelf's `pyproject.toml`.
2. The justfile: not copied. `blueprint render` writes the blueprint-owned parts (`.blueprint/base.just` and one per stack) and the
   repo's `justfile` imports them (ADR 0029), so a consumer holds no copy of the gate's recipe text and `blueprint render --check` is
   its drift check. Only `bootstrap` and `bootstrap-verify` (this onboarding, which needs a shelf clone) are still copied, and only
   when the repo has no recipe of its own by that name. The gate's shelf packages (`any-gate`, `any-gate-python`, `blueprint`) are
   added as dev dependencies when absent.
3. The `dev` dependency-group.
4. A `[tool.pyrefly]` and a `[tool.pytest.ini_options]` built for a consumer: the shelf's strict
   preset and error severities (the axis `just preset` compares), its lighter bar for tests, and
   none of the shelf's own include/exclude/search paths or testpaths.

ADR 0004 — "linters are a config-preset, not a CLI" — means this is a
**one-shot scaffold**, not a syncing tool: copy, then the consumer owns it (the justfile is the exception: it is rendered).
That is also why the merge granularity is per-table / per-recipe, never
per-line: **a repo that already has its own `[tool.ruff]` keeps it exactly as
written** — this operation appends only what is genuinely absent, and never
opens an existing table to negotiate with its contents. `docs/linting.md`
itself says "own it" — line-level reconciliation is the consumer's judgment,
not this operation's to make.

Effect-assertion: after writing, `pyproject.toml` is re-parsed with `tomllib`
(catches injected syntax errors — a byte count matching is not proof the file
is still valid TOML), and `just --dry-run check` runs in the repo: every recipe the gate
names must resolve. Checking that recipe names were written was not enough —
shelf-4mz shipped a `check` that depended on a `preset` target never copied.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .hooks import ensure_gate_dependency
from .operations import Outcome, Result

_SHELF_ROOT = Path(__file__).resolve().parent.parent.parent
# blueprint is plain stdlib python: onboarding runs from a shelf clone with no install, so it reads the package from there.
_BLUEPRINT_SRC = str(_SHELF_ROOT / "packages" / "blueprint" / "src")
if _BLUEPRINT_SRC not in sys.path:
    sys.path.insert(0, _BLUEPRINT_SRC)
from blueprint import render  # noqa: E402 -- after the path above

_SHELF_PYPROJECT = _SHELF_ROOT / "pyproject.toml"
_SHELF_JUSTFILE = _SHELF_ROOT / "justfile"
_JUSTFILES = ("justfile", "Justfile", ".justfile")

_TABLE_PREFIXES = ("tool.ruff", "tool.codespell", "tool.coverage", "tool.shelf-size")
_DEV_GROUP_TABLE = "dependency-groups"
# Shelf-specific ruff tables a consumer must not inherit: the banned-api list bans the consumer apps
# (a2kay, ...), which would ban a consumer from importing itself.
_SHELF_ONLY_TABLES = ("tool.ruff.lint.flake8-tidy-imports",)
_BOOTSTRAP_RECIPES = ("bootstrap", "bootstrap-verify")

_GENERATED_PREFIXES = ("tool.pyrefly", "tool.pytest")
_SHELF_TESTS_SUBCONFIG = "packages/*/tests/**"
_CONSUMER_PYTEST = """[tool.pytest.ini_options]
addopts = "-ra --strict-markers"

"""

_TOML_HEADER_RE = re.compile(r"^\[([^\]]+)\]\s*$", re.MULTILINE)
# `name:`, `name arg:`, `name *args: dep`; a `name := value` assignment is not a recipe (`:=`), nor is `set x := y`.
_JUST_RECIPE_RE = re.compile(r"^@?([A-Za-z_][A-Za-z0-9_-]*)(?:[ \t]+[^:=\n]*?)?[ \t]*:(?!=)")


def _split_toml_tables(text: str) -> list[tuple[str, str]]:
    """Top-level `[name]` tables, in file order, as `(name, block_text_incl_header)`."""
    matches = list(_TOML_HEADER_RE.finditer(text))
    return [(m.group(1), text[m.start() : (matches[i + 1].start() if i + 1 < len(matches) else len(text))]) for i, m in enumerate(matches)]


def _split_just_recipes(text: str) -> list[tuple[str, str]]:
    """Recipes in file order, as `(name, block_text)`: the comment and `[attribute]` lines directly above a recipe belong to it."""
    lines = text.splitlines(keepends=True)
    starts: list[tuple[str, int]] = []
    for i, line in enumerate(lines):
        if m := _JUST_RECIPE_RE.match(line):
            first = i
            while first > 0 and lines[first - 1].startswith(("#", "[")):
                first -= 1
            starts.append((m.group(1), first))
    return [
        (name, "".join(lines[first : starts[k + 1][1] if k + 1 < len(starts) else len(lines)])) for k, (name, first) in enumerate(starts)
    ]


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
        if name.startswith(_TABLE_PREFIXES)
        and not name.startswith(_SHELF_ONLY_TABLES)
        and not any(name == p or name.startswith(p + ".") for p in owned_prefixes)
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
        f"[tool.pyrefly]\npreset = {_toml_value(shelf['preset'])}\nuse-ignore-files = false\n\n[tool.pyrefly.errors]\n{errors}\n"
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
    """`None` when every recipe `just check` names resolves; otherwise just's complaint."""
    exe = shutil.which("just") or (str(venv) if (venv := repo / ".venv" / "bin" / "just").is_file() else None)
    if exe is None:
        return "just is not installed -- cannot verify the copied gate (pin it: `uv add --dev rust-just`, then `uv sync`)"
    dry = subprocess.run([exe, "--dry-run", "check"], cwd=repo, capture_output=True, text=True, check=False)
    if dry.returncode == 0:
        return None
    lines = (dry.stderr.strip() or dry.stdout.strip()).splitlines()
    return next((line for line in lines if line.startswith("error")), lines[-1] if lines else "no output")


def _recipes_to_copy(target_text: str) -> list[str]:
    target_names = {name for name, _ in _split_just_recipes(target_text)}
    # `bootstrap-verify: bootstrap` is meaningless on its own: a consumer that owns an unrelated `bootstrap:` (a common name) must not get
    # a `bootstrap-verify` that silently aliases to it.
    if "bootstrap" in target_names:
        return [name for name in _BOOTSTRAP_RECIPES if name not in target_names and name != "bootstrap-verify"]
    return [name for name in _BOOTSTRAP_RECIPES if name not in target_names]


@dataclass
class LinterPresetOperation:
    """Copies missing `pyproject.toml` tables and `justfile` recipes from shelf into `repo` (python+uv only)."""

    repo: Path
    name: str = "linter-preset"
    requires: tuple[str, ...] = ()

    def run(self, _results: dict[str, Result]) -> Result:
        """Copy every shelf table/recipe family not already owned by `repo`."""
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

        rendered = render.write(self.repo)
        if rendered:
            applied.append(f"justfile parts ({', '.join(rendered)})")
        justfile = next((self.repo / n for n in _JUSTFILES if (self.repo / n).is_file()), self.repo / "justfile")
        existing = justfile.read_text()
        to_copy = _recipes_to_copy(existing)
        if to_copy:
            shelf_recipes = dict(_split_just_recipes(_SHELF_JUSTFILE.read_text()))
            justfile.write_text(existing.rstrip("\n") + "\n\n" + "".join(shelf_recipes[name] for name in to_copy))
            applied.append(f"{justfile.name} recipes")
        if ensure_gate_dependency(self.repo):
            applied.append("pyproject.toml any-gate dev dependency")

        return _verify(self.repo, applied, to_copy, justfile)


def _verify(repo: Path, applied: list[str], to_copy: list[str], justfile: Path) -> Result:
    """Assert the effect: valid TOML, every copied recipe present, and `just --dry-run check` resolving."""
    pyproject = repo / "pyproject.toml"
    done = f"copied {', '.join(applied)}" if applied else "already current — nothing to copy"
    try:
        pyproject_text = pyproject.read_text()
        tomllib.loads(pyproject_text)
    except tomllib.TOMLDecodeError as exc:
        return Result(Outcome.FAILED, verified=False, message=f"{pyproject} is not valid TOML after writing: {exc}")
    written = {name for name, _ in _split_just_recipes(justfile.read_text())} if justfile.exists() else set()
    if missing := set(to_copy) - written:
        return Result(Outcome.FAILED, verified=False, message=f"{justfile.name} still missing recipes after write: {missing}")
    if justfile.exists() and (complaint := _gate_resolves(repo)):
        return Result(Outcome.FAILED, verified=False, message=f"{done}, but `just check` does not resolve: {complaint}")
    notes = []
    if "rust-just" not in pyproject_text:
        notes.append("pin the runner: `uv add --dev rust-just`")
    if (repo / "Makefile").is_file() and justfile.name != "Makefile":
        notes.append("a Makefile still sits beside the justfile: port its targets, then delete it")
    return Result(Outcome.APPLIED, verified=True, message=done + (f" ({'; '.join(notes)})" if notes else ""))
