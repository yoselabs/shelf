"""Guard: a consumer's linter config matches the shelf's, or says why not.

The shelf's `pyproject.toml` IS the linter preset (ADR 0004) and a consumer inherits it by **copying**: "inherit the judgment, own the
result". That resolution also says drift is acceptable *and visible*. `blueprint init` is append-only by design, so it
reports "already current" for a repo missing two whole rule families, which is how ten repos here reached ten different rule sets with no
one deciding to.

This closes that loop without taking the ownership away. It compares two axes (`[tool.ruff.lint] select`/`ignore`,
and `[tool.pyrefly.errors]`) plus the ruff and pyrefly versions both `uv.lock` files hold and the shared `[tool.shelf-size]` caps. The
justfile is not compared here: its parts are rendered, and `blueprint gate render --check` is the drift check on them (ADR 0029). Size
differences always fail; other differences fail unless the consumer declares them in its own::

    [tool.shelf-preset]
    ruff-select-omitted = []
    pyrefly-errors-extra = ["unknown-argument-type"]  # reflective verb dispatch
    linter-versions-differ = ["ruff"]                 # trying ruff 0.17 ahead of the shelf

An empty list means "identical here". A
declared entry is a local choice made on purpose, in the consumer's own file, next to a reason. An *undeclared* one is drift, and that is
the only thing this fails on: it never edits, never proposes a value, and has no opinion about which side is right.

The ruff axes come from the config ruff reads: a `.ruff.toml` or `ruff.toml` beside pyproject.toml wins over its `[tool.ruff]` (the
file's `[lint]` is compared), and a shadowed block fails unless `ruff-config-shadows = ["ruff.toml"]` declares it.

Deliberately NOT compared: `per-file-ignores` keys and `sub-config` matches. Those are paths, and a consumer's tree is not the shelf's.

The reference is `preset.toml` beside this file: a snapshot of the shelf's own config, so a consumer needs no shelf clone. The shelf
regenerates it with `tools/preset_refresh/preset_refresh.py` (not shipped) and a test fails when it is stale.

Exit codes: 0 no undeclared drift · 1 drift · 2 could not check (unreadable reference or config). A check that cannot run is never a pass.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

from blueprint.model import python_folder

REFERENCE = Path(__file__).resolve().parent / "preset.toml"

# Every axis this compares, and the `[tool.shelf-preset]` keys that excuse a difference on it. `omitted` = the shelf has it and the
# consumer does not; `extra` = the reverse.
_AXES = (
    ("ruff-select", "ruff select"),
    ("ruff-ignore", "ruff ignore"),
    ("pyrefly-errors", "pyrefly error kinds"),
)

# The linters whose version is part of the rule set: one config under two ruff versions is two rule sets.
_LINTERS = ("ruff", "pyrefly")


def _load(path: Path) -> dict[str, Any]:
    with path.open("rb") as fh:
        return tomllib.load(fh)


# Ruff reads the nearest of these in a folder, first one wins; a `[tool.ruff]` table in pyproject.toml comes last.
_RUFF_FILES = (".ruff.toml", "ruff.toml")


def _ruff(config: dict[str, Any], key: str) -> set[str]:
    return set(config.get("tool", {}).get("ruff", {}).get("lint", {}).get(key, []))


def _effective_ruff(repo: Path, consumer: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """The config ruff reads in `repo`, shaped as a pyproject (`tool.ruff`), and the file name when that file is not pyproject.toml."""
    for name in _RUFF_FILES:
        if (repo / name).is_file():
            return {"tool": {"ruff": _load(repo / name)}}, name
    return consumer, None


def _pyrefly_errors(config: dict[str, Any]) -> set[str]:
    """Kinds raised to `error`. A kind set `false` is a recorded rejection, not a rule."""
    errors = config.get("tool", {}).get("pyrefly", {}).get("errors", {})
    return {kind for kind, severity in errors.items() if severity == "error"}


def _locked_linters(repo: Path) -> dict[str, str]:
    """name -> version of each linter in the repo's uv.lock; empty when there is no lock."""
    path = repo / "uv.lock"
    if not path.is_file():
        return {}
    packages = tomllib.loads(path.read_text()).get("package", [])
    return {str(p["name"]): str(p.get("version", "")) for p in packages if p.get("name") in _LINTERS}


def snapshot(shelf: Path) -> dict[str, Any]:  # Any: TOML-bound, lists and one table
    """What a consumer is compared against, read from the shelf's own files."""
    config = _load(shelf / "pyproject.toml")
    return {
        "ruff-select": sorted(_ruff(config, "select")),
        "ruff-ignore": sorted(_ruff(config, "ignore")),
        "pyrefly-errors": sorted(_pyrefly_errors(config)),
        "linters": _locked_linters(shelf),
        "shelf-size": config.get("tool", {}).get("shelf-size", {}),
    }


def toml_value(item: Any) -> str:  # Any: a TOML value of any kind
    if isinstance(item, list):
        return "[" + ", ".join(toml_value(v) for v in item) + "]"
    if isinstance(item, bool):
        return "true" if item else "false"
    if isinstance(item, int):
        return str(item)
    return '"' + str(item).replace("\\", "\\\\").replace('"', '\\"') + '"'


def render(snap: dict[str, Any]) -> str:  # Any: TOML-bound snapshot
    """The snapshot as TOML text: plain, so any reader of it (a Rust blueprint included) needs no Python."""
    lines = ["# The shelf's linter preset, derived from its own files. Never hand-edit.", ""]
    lines += [f"{key} = {toml_value(val)}" for key, val in snap.items() if not isinstance(val, dict)]
    for key, val in snap.items():
        if isinstance(val, dict):
            lines += ["", f"[{key}]", *(f"{name} = {toml_value(item)}" for name, item in sorted(val.items()))]
    return "\n".join(lines) + "\n"


def is_shelf(repo: Path) -> bool:
    """The repo that owns the snapshot (it holds `preset.toml` in its blueprint package): it IS the preset, so it compares to nothing."""
    return (repo / "packages" / "blueprint" / "src" / "blueprint" / REFERENCE.name).is_file()


def _compare(axis: str, shelf: set[str], consumer: set[str], declared: dict[str, Any]) -> list[str]:
    """Undeclared differences on one axis, as printable lines."""
    omitted = shelf - consumer - set(declared.get(f"{axis}-omitted", []))
    extra = consumer - shelf - set(declared.get(f"{axis}-extra", []))
    return [f"  {axis}: missing {item!r} (the shelf has it)" for item in sorted(omitted)] + [
        f"  {axis}: extra {item!r} (the shelf does not)" for item in sorted(extra)
    ]


def size_drift(reference: dict[str, Any], consumer: dict[str, Any]) -> list[str]:  # Any: two parsed pyproject files
    """Size caps are a shared contract, with no exception declarations."""
    expected = reference.get("tool", {}).get("shelf-size", {})
    actual = consumer.get("tool", {}).get("shelf-size", {})
    return [] if expected == actual else [f"  shelf-size: expected {expected!r}, got {actual!r}"]


def _version_drift(reference: dict[str, str], repo: Path, declared: dict[str, Any]) -> list[str]:
    """Each linter both hold at different versions, unless `linter-versions-differ` names it."""
    theirs = _locked_linters(repo)
    excused = set(declared.get("linter-versions-differ", []))
    return [
        f"  linter-versions: {name} {theirs[name]} here, {reference[name]} in the shelf (the same config, other rules)"
        for name in _LINTERS
        if name in reference and name in theirs and reference[name] != theirs[name] and name not in excused
    ]


def _shadow(consumer: dict[str, Any], ruff_file: str | None, declared: dict[str, Any]) -> list[str]:
    """A ruff file beside a `[tool.ruff]` block: ruff reads the file, so the block is dead, unless the consumer says so on purpose."""
    if ruff_file is None or "ruff" not in consumer.get("tool", {}) or ruff_file in declared.get("ruff-config-shadows", []):
        return []
    what = f"{ruff_file} shadows [tool.ruff] in pyproject.toml: ruff reads {ruff_file} and ignores the block"
    how = f'(compared here: {ruff_file}); delete one, or declare ruff-config-shadows = ["{ruff_file}"]'
    return [f"  {what} {how}"]


def check(repo: Path, reference_file: Path | None = None) -> int:
    """Compare `repo` with the preset; the exit code of `blueprint gate preset`."""
    repo = repo / (python_folder(repo) or ".")  # the Python stack's folder (ADR 0034): its pyproject.toml, ruff config and uv.lock
    consumer_toml = repo / "pyproject.toml"
    if not consumer_toml.is_file():
        sys.stderr.write(f"preset-drift: no pyproject.toml at {repo} -- CANNOT VERIFY, not a pass\n")
        return 2
    if reference_file is None and is_shelf(repo):
        sys.stdout.write("preset-drift: this IS the shelf; nothing to compare against\n")
        return 0
    try:
        consumer = _load(consumer_toml)
        reference = _load(reference_file or REFERENCE)
    except (tomllib.TOMLDecodeError, OSError) as exc:
        sys.stderr.write(f"preset-drift: unreadable config or reference ({exc}) -- CANNOT VERIFY, not a pass\n")
        return 2

    declared = consumer.get("tool", {}).get("shelf-preset", {})
    try:
        effective, ruff_file = _effective_ruff(repo, consumer)
    except (tomllib.TOMLDecodeError, OSError) as exc:
        sys.stderr.write(f"preset-drift: unreadable ruff config ({exc}) -- CANNOT VERIFY, not a pass\n")
        return 2
    values = {
        "ruff-select": _ruff(effective, "select"),
        "ruff-ignore": _ruff(effective, "ignore"),
        "pyrefly-errors": _pyrefly_errors(consumer),
    }
    findings = _shadow(consumer, ruff_file, declared)
    findings += [line for axis, _ in _AXES for line in _compare(axis, set(reference.get(axis, [])), values[axis], declared)]
    findings += _version_drift(reference.get("linters", {}), repo, declared)
    findings += size_drift({"tool": {"shelf-size": reference.get("shelf-size", {})}}, consumer)
    if not findings:
        sys.stdout.write(f"preset-drift: {repo.name} matches the shelf preset (or declares every difference)\n")
        return 0
    sys.stderr.write(f"preset-drift: {len(findings)} undeclared difference(s) from the shelf preset:\n")
    sys.stderr.write("".join(f"{line}\n" for line in findings))
    sys.stderr.write(
        "\nEither converge, or declare the difference with its reason in [tool.shelf-preset] in your pyproject.toml. "
        "See the shelf's docs/linting.md.\n"
    )
    return 1
