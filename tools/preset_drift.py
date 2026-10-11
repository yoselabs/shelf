#!/usr/bin/env python3
"""Guard: a consumer's linter config matches the shelf's, or says why not.

The shelf's ``pyproject.toml`` IS the linter preset (ADR 0004) and a
consumer inherits it by **copying** — "inherit the judgment, own the result".
That resolution also says drift is acceptable *and visible*. It was not visible.
``tools/onboard/linter_preset.py`` is append-only by design, so it reports
"already current" for a repo missing two whole rule families, which is how ten
repos here reached ten different rule sets with no one deciding to.

This closes that loop without taking the ownership away. It compares three axes —
``[tool.ruff.lint] select``/``ignore``, ``[tool.pyrefly.errors]``, and the
``justfile`` recipe set (a consumer still on a ``Makefile`` is compared by its targets) — plus the ruff and pyrefly
versions both ``uv.lock`` files hold, and fails on any difference the consumer has not declared in its own::

    [tool.shelf-preset]
    ruff-select-omitted = []
    pyrefly-errors-extra = ["unknown-argument-type"]  # reflective verb dispatch
    recipes-extra = ["archlint"]                      # import-linter contracts
    linter-versions-differ = ["ruff"]                 # trying ruff 0.17 ahead of the shelf

(``make-targets-extra`` / ``make-targets-omitted``, this axis's name before ADR 0023, still count.)
An empty list means "identical here". A declared entry is a local choice made on
purpose, in the consumer's own file, next to a reason. An *undeclared* one is
drift, and that is the only thing this fails on — it never edits, never proposes
a value, and has no opinion about which side is right.

Deliberately NOT compared: ``per-file-ignores`` keys and ``sub-config`` matches.
Those are paths, and a consumer's tree is not the shelf's; comparing them would
fail on every consumer forever, which trains everyone to ignore the check.

Exit codes: ``0`` no undeclared drift · ``1`` drift · ``2`` could not check
(no shelf clone, unreadable config). A check that cannot run is never reported
as a pass.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

# Every axis this compares, and the `[tool.shelf-preset]` keys that excuse a
# difference on it. `omitted` = the shelf has it and the consumer does not;
# `extra` = the reverse.
_AXES = (
    ("ruff-select", "ruff select"),
    ("ruff-ignore", "ruff ignore"),
    ("pyrefly-errors", "pyrefly error kinds"),
    ("recipes", "gate recipes"),
)

# A recipe header: `name:`, `name arg:`, `name *args: dep`; an assignment (`:=`) and `set x := y` are not recipes.
_RECIPE = re.compile(r"^@?([A-Za-z_][\w-]*)(?:[ \t]+[^:=\n]*?)?[ \t]*:(?!=)")
_JUSTFILES = ("justfile", "Justfile", ".justfile")

# Recipes that operate on the shelf's own layout (its catalog, its cross-package
# advisory, its import-graph contracts (`arch`: a consumer's layers are its own), its
# any-browser lane, its gate container and affected-only run). `blueprint`
# is copied (the per-commit blueprint checks), so it is not shelf-only. A consumer
# has nothing for them to act on, so their absence is not drift; without this every
# fresh consumer failed `just preset`.
_SHELF_ONLY_TARGETS = frozenset(
    {
        "catalog",
        "advisory",
        "arch",
        "test-browser",
        "check-all",
        "check-host",
        "check-all-host",
        "test-image",
        "test-affected",
        "eval",
        "gate",
        "container",
        "images",
    }
)


def _load(path: Path) -> dict[str, Any]:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _ruff(config: dict[str, Any], key: str) -> set[str]:
    lint = config.get("tool", {}).get("ruff", {}).get("lint", {})
    return set(lint.get(key, []))


def _pyrefly_errors(config: dict[str, Any]) -> set[str]:
    """Kinds raised to ``error``. A kind set ``false`` is a recorded rejection, not a rule."""
    errors = config.get("tool", {}).get("pyrefly", {}).get("errors", {})
    return {kind for kind, severity in errors.items() if severity == "error"}


def _recipes(repo: Path) -> set[str]:
    """The names in the repo's justfile, else in its Makefile (a consumer not yet migrated); empty when it has neither."""
    for name in (*_JUSTFILES, "Makefile"):
        if (path := repo / name).is_file():
            return {m.group(1) for line in path.read_text().splitlines() if (m := _RECIPE.match(line))}
    return set()


# The linters whose version is part of the rule set: one config under two ruff versions is two rule sets.
_LINTERS = ("ruff", "pyrefly")


def _locked(repo: Path) -> dict[str, str]:
    """name -> version of each linter in the repo's uv.lock; empty when there is no lock."""
    path = repo / "uv.lock"
    if not path.is_file():
        return {}
    packages = tomllib.loads(path.read_text()).get("package", [])
    return {str(p["name"]): str(p.get("version", "")) for p in packages if p.get("name") in _LINTERS}


def _version_drift(shelf: Path, repo: Path, declared: dict[str, Any]) -> list[str]:
    """Each linter both locks hold at different versions, unless `linter-versions-differ` names it."""
    ours, theirs = _locked(shelf), _locked(repo)
    excused = set(declared.get("linter-versions-differ", []))
    return [
        f"  linter-versions: {name} {theirs[name]} here, {ours[name]} in the shelf (the same config, other rules)"
        for name in _LINTERS
        if name in ours and name in theirs and ours[name] != theirs[name] and name not in excused
    ]


def _shelf_root(explicit: str | None) -> Path | None:
    """Resolve the shelf the way ``just guard`` does, so one answer is wrong in one place.

    An explicit ``--shelf-home`` does NOT fall back. Searching on from a path the
    caller named would silently check against a different shelf than the one they
    asked for, and report a pass for it.
    """
    if explicit is not None:
        path = Path(explicit).expanduser()
        return path.resolve() if (path / "pyproject.toml").is_file() else None
    for candidate in (os.environ.get("SHELF_HOME"), "../shelf", str(Path.home() / "Workspaces" / "shelf")):
        if candidate and (path := Path(candidate).expanduser()).joinpath("pyproject.toml").is_file():
            return path.resolve()
    return None


def _compare(axis: str, shelf: set[str], consumer: set[str], declared: dict[str, Any]) -> list[str]:
    """Undeclared differences on one axis, as printable lines."""
    omitted = shelf - consumer - set(declared.get(f"{axis}-omitted", []))
    extra = consumer - shelf - set(declared.get(f"{axis}-extra", []))
    return [f"  {axis}: missing {item!r} (the shelf has it)" for item in sorted(omitted)] + [
        f"  {axis}: extra {item!r} (the shelf does not)" for item in sorted(extra)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=".", help="the consumer repo to check (default: cwd)")
    parser.add_argument("--shelf-home", default=None, help="the shelf clone (default: $SHELF_HOME, ../shelf, ~/Workspaces/shelf)")
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    consumer_toml = repo / "pyproject.toml"
    if not consumer_toml.is_file():
        print(f"preset-drift: no pyproject.toml at {repo} -- CANNOT VERIFY, not a pass", file=sys.stderr)
        return 2

    # A worktree of the shelf is the shelf, and its `../shelf` resolves to the main
    # checkout — so identity is "this script lives in the repo under test", not a path
    # comparison. Without it, `just preset` in a shelf worktree grades the branch
    # against `main` and fails on every change the branch is making. Checked before the
    # clone lookup: the shelf's own gate container has no clone beside it.
    shelf = _shelf_root(args.shelf_home)
    if Path(__file__).resolve().parent.parent == repo or shelf == repo:
        print("preset-drift: this IS the shelf; nothing to compare against")
        return 0
    if shelf is None:
        print("preset-drift: shelf clone not found (set SHELF_HOME) -- CANNOT VERIFY, not a pass", file=sys.stderr)
        return 2

    try:
        consumer = _load(consumer_toml)
        reference = _load(shelf / "pyproject.toml")
    except tomllib.TOMLDecodeError as exc:
        print(f"preset-drift: unreadable config ({exc}) -- CANNOT VERIFY, not a pass", file=sys.stderr)
        return 2

    declared = consumer.get("tool", {}).get("shelf-preset", {})
    # This axis was called make-targets before ADR 0023; a consumer's declaration under the old name still excuses.
    for suffix in ("omitted", "extra"):
        declared[f"recipes-{suffix}"] = [*declared.get(f"recipes-{suffix}", []), *declared.get(f"make-targets-{suffix}", [])]
    values = {
        "ruff-select": (_ruff(reference, "select"), _ruff(consumer, "select")),
        "ruff-ignore": (_ruff(reference, "ignore"), _ruff(consumer, "ignore")),
        "pyrefly-errors": (_pyrefly_errors(reference), _pyrefly_errors(consumer)),
        # A shelf-only recipe is neither owed nor extra: a consumer may copy the dispatch pattern (`gate`, a2kay: shelf-cld).
        "recipes": (_recipes(shelf) - _SHELF_ONLY_TARGETS, _recipes(repo) - _SHELF_ONLY_TARGETS),
    }

    findings = [line for axis, _ in _AXES for line in _compare(axis, *values[axis], declared)]
    findings += _version_drift(shelf, repo, declared)
    if not findings:
        print(f"preset-drift: {repo.name} matches the shelf preset (or declares every difference)")
        return 0

    print(f"preset-drift: {len(findings)} undeclared difference(s) from the shelf preset ({shelf}):", file=sys.stderr)
    for line in findings:
        print(line, file=sys.stderr)
    print(
        "\nEither converge, or declare the difference with its reason in "
        "[tool.shelf-preset] in your pyproject.toml. See the shelf's docs/linting.md.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
