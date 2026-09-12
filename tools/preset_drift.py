#!/usr/bin/env python3
"""Guard: a consumer's linter config matches the shelf's, or says why not.

The shelf's ``pyproject.toml`` IS the linter preset (resolution 0004) and a
consumer inherits it by **copying** — "inherit the judgment, own the result".
That resolution also says drift is acceptable *and visible*. It was not visible.
``tools/onboard/linter_preset.py`` is append-only by design, so it reports
"already current" for a repo missing two whole rule families, which is how ten
repos here reached ten different rule sets with no one deciding to.

This closes that loop without taking the ownership away. It compares three axes —
``[tool.ruff.lint] select``/``ignore``, ``[tool.pyrefly.errors]``, and the
``Makefile`` target set — and fails on any difference the consumer has not
declared in its own::

    [tool.shelf-preset]
    ruff-select-omitted = []
    pyrefly-errors-extra = ["unknown-argument-type"]  # reflective verb dispatch
    make-targets-extra = ["archlint"]                 # import-linter contracts

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
    ("make-targets", "make targets"),
)

_TARGET = re.compile(r"^([a-zA-Z][\w-]*)\s*:(?!=)")


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


def _make_targets(makefile: Path) -> set[str]:
    if not makefile.is_file():
        return set()
    return {m.group(1) for line in makefile.read_text().splitlines() if (m := _TARGET.match(line))}


def _shelf_root(explicit: str | None) -> Path | None:
    """Resolve the shelf the way ``make guard`` does, so one answer is wrong in one place.

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

    shelf = _shelf_root(args.shelf_home)
    if shelf is None:
        print("preset-drift: shelf clone not found (set SHELF_HOME) -- CANNOT VERIFY, not a pass", file=sys.stderr)
        return 2
    # A worktree of the shelf is the shelf, and its `../shelf` resolves to the main
    # checkout — so identity is "this script lives in the repo under test", not a path
    # comparison. Without it, `make preset` in a shelf worktree grades the branch
    # against `main` and fails on every change the branch is making.
    if shelf == repo or Path(__file__).resolve().parent.parent == repo:
        print("preset-drift: this IS the shelf; nothing to compare against")
        return 0

    try:
        consumer = _load(consumer_toml)
        reference = _load(shelf / "pyproject.toml")
    except tomllib.TOMLDecodeError as exc:
        print(f"preset-drift: unreadable config ({exc}) -- CANNOT VERIFY, not a pass", file=sys.stderr)
        return 2

    declared = consumer.get("tool", {}).get("shelf-preset", {})
    values = {
        "ruff-select": (_ruff(reference, "select"), _ruff(consumer, "select")),
        "ruff-ignore": (_ruff(reference, "ignore"), _ruff(consumer, "ignore")),
        "pyrefly-errors": (_pyrefly_errors(reference), _pyrefly_errors(consumer)),
        "make-targets": (_make_targets(shelf / "Makefile"), _make_targets(repo / "Makefile")),
    }

    findings = [line for axis, _ in _AXES for line in _compare(axis, *values[axis], declared)]
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
