"""`python -m any_knowledge`: `index [--write]`, `check` and `seed`, each over `--repo` (default: the current directory).

`index` prints docs/adr/INDEX.md as the ADRs generate it, or writes it. `check` exits 1 on a malformed ADR or a stale index, and with
`--glossary` on a missing CONTEXT.md; a repo with no docs/adr/ is not judged. `seed` copies the missing docs/agents files and keeps the
AGENTS.md managed block (`--stack`, `--framework`, `--beads` say what the repo is).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from any_knowledge import adr, checks, templates

if TYPE_CHECKING:
    from collections.abc import Sequence


def _index(args: argparse.Namespace) -> int:
    text = adr.index(args.repo.resolve())
    if args.write:
        (args.repo / adr.FOLDER / adr.INDEX).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


def _check(args: argparse.Namespace) -> int:
    repo = args.repo.resolve()
    found = [*checks.adr_format(repo), *checks.adr_index(repo), *(checks.glossary(repo) if args.glossary else [])]
    for line in found:
        sys.stderr.write(f"{line}\n")
    if found:
        sys.stderr.write(f"format: {checks.FORMAT}; index: {checks.REGENERATE}\n")
    return 1 if found else 0


def _seed(args: argparse.Namespace) -> int:
    chosen = templates.Selection(tuple(args.stack), tuple(args.framework), args.beads)
    for path in templates.install(args.repo.resolve(), chosen):
        sys.stdout.write(f"{path}\n")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="any_knowledge", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn, text in (
        ("index", _index, "print docs/adr/INDEX.md as the ADRs generate it"),
        ("check", _check, "fail on a malformed ADR or a stale index"),
        ("seed", _seed, "copy the missing docs/agents files and the AGENTS.md block"),
    ):
        sp = sub.add_parser(name, help=text, description=text)
        sp.add_argument("--repo", type=Path, default=Path())
        sp.set_defaults(run=fn)
        if name == "index":
            sp.add_argument("--write", action="store_true", help="write docs/adr/INDEX.md instead of printing")
        if name == "check":
            sp.add_argument("--glossary", action="store_true", help="also require CONTEXT.md")
        if name == "seed":
            sp.add_argument("--stack", action="append", default=[], help="a stack the repo has (python-uv, dotnet, nix, compose, shell)")
            sp.add_argument("--framework", action="append", default=[], help="a framework the repo uses (godot, mcp, unity)")
            sp.add_argument("--beads", action="store_true", help="the repo tracks work in beads")
    args = parser.parse_args(argv)
    return int(args.run(args))
