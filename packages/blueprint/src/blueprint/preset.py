"""Guard: a consumer's linter config matches the shelf's, or says why not.

The shelf's `pyproject.toml` IS the linter preset (ADR 0004) and a consumer inherits it by **copying**: "inherit the judgment, own the
result". That resolution also says drift is acceptable *and visible*. `tools/onboard/linter_preset.py` is append-only by design, so it
reports "already current" for a repo missing two whole rule families, which is how ten repos here reached ten different rule sets with no
one deciding to.

This closes that loop without taking the ownership away. It compares two axes (`[tool.ruff.lint] select`/`ignore`,
and `[tool.pyrefly.errors]`) plus the ruff and pyrefly versions both `uv.lock` files hold and the shared `[tool.shelf-size]` caps. The
justfile is not compared here: its parts are rendered, and `blueprint render --check` is the drift check on them (ADR 0029). Size
differences always fail; other differences fail unless the consumer declares them in its own::

    [tool.shelf-preset]
    ruff-select-omitted = []
    pyrefly-errors-extra = ["unknown-argument-type"]  # reflective verb dispatch
    linter-versions-differ = ["ruff"]                 # trying ruff 0.17 ahead of the shelf

An empty list means "identical here". A
declared entry is a local choice made on purpose, in the consumer's own file, next to a reason. An *undeclared* one is drift, and that is
the only thing this fails on: it never edits, never proposes a value, and has no opinion about which side is right.

Deliberately NOT compared: `per-file-ignores` keys and `sub-config` matches. Those are paths, and a consumer's tree is not the shelf's.

The reference is `preset.toml` beside this file: a snapshot of the shelf's own config, so a consumer needs no shelf clone. The shelf
regenerates it with `blueprint preset --refresh` and a test fails when it is stale.

Exit codes: 0 no undeclared drift · 1 drift · 2 could not check (unreadable reference or config). A check that cannot run is never a pass.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

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


def _ruff(config: dict[str, Any], key: str) -> set[str]:
    return set(config.get("tool", {}).get("ruff", {}).get("lint", {}).get(key, []))


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


def snapshot(shelf: Path) -> dict[str, Any]:
    """What a consumer is compared against, read from the shelf's own files."""
    config = _load(shelf / "pyproject.toml")
    return {
        "ruff-select": sorted(_ruff(config, "select")),
        "ruff-ignore": sorted(_ruff(config, "ignore")),
        "pyrefly-errors": sorted(_pyrefly_errors(config)),
        "linters": _locked_linters(shelf),
        "shelf-size": config.get("tool", {}).get("shelf-size", {}),
    }


def _value(value: Any) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(_value(v) for v in value) + "]"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def render(snap: dict[str, Any]) -> str:
    """The snapshot as TOML text: plain, so any reader of it (a Rust blueprint included) needs no Python."""
    lines = ["# The shelf's linter preset, derived from its own files by `blueprint preset --refresh`. Never hand-edit.", ""]
    lines += [f"{key} = {_value(val)}" for key, val in snap.items() if not isinstance(val, dict)]
    for key, val in snap.items():
        if isinstance(val, dict):
            lines += ["", f"[{key}]", *(f"{name} = {_value(item)}" for name, item in sorted(val.items()))]
    return "\n".join(lines) + "\n"


def is_shelf(repo: Path) -> bool:
    """The repo that owns the snapshot (it holds `preset.toml` in its blueprint package): it IS the preset, so it compares to nothing."""
    return (repo / "packages" / "blueprint" / "src" / "blueprint" / REFERENCE.name).is_file()


def refresh(shelf: Path) -> Path:
    path = shelf / "packages" / "blueprint" / "src" / "blueprint" / REFERENCE.name
    path.write_text(render(snapshot(shelf)))
    return path


def _compare(axis: str, shelf: set[str], consumer: set[str], declared: dict[str, Any]) -> list[str]:
    """Undeclared differences on one axis, as printable lines."""
    omitted = shelf - consumer - set(declared.get(f"{axis}-omitted", []))
    extra = consumer - shelf - set(declared.get(f"{axis}-extra", []))
    return [f"  {axis}: missing {item!r} (the shelf has it)" for item in sorted(omitted)] + [
        f"  {axis}: extra {item!r} (the shelf does not)" for item in sorted(extra)
    ]


def size_drift(reference: dict[str, Any], consumer: dict[str, Any]) -> list[str]:
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


def check(repo: Path, reference_file: Path | None = None) -> int:
    """Compare `repo` with the preset; the exit code of `blueprint preset`."""
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
    values = {
        "ruff-select": _ruff(consumer, "select"),
        "ruff-ignore": _ruff(consumer, "ignore"),
        "pyrefly-errors": _pyrefly_errors(consumer),
    }
    findings = [line for axis, _ in _AXES for line in _compare(axis, set(reference.get(axis, [])), values[axis], declared)]
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
