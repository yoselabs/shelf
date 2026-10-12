"""A test helper: walk a CLI's ``--help`` tree and assert it explains itself (ADR 0025).

:func:`assert_help_tree` runs ``--help`` on the parser and on every subcommand, recursively, and
checks that it exits 0, that a description sits between the usage and the arguments, that no
option or positional lacks help, and that every subcommand is listed with text. Stdlib only.

A subparser added with ``help=None`` (the default) is left out of its parent's listing by
argparse, so it needs ``help=`` as well as ``description=``.
"""

from __future__ import annotations

import argparse
import contextlib
import io
from typing import Any


def assert_help_tree(parser: argparse.ArgumentParser, *, prog: str | None = None) -> None:
    """Raise ``AssertionError`` naming every command whose ``--help`` does not explain itself."""
    problems: list[str] = []
    _walk(parser, prog or parser.prog, problems)
    if problems:
        raise AssertionError("--help tree is not self-explaining:\n  " + "\n  ".join(problems))


def _walk(parser: argparse.ArgumentParser, path: str, problems: list[str]) -> None:
    out = io.StringIO()
    code: Any = None
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            parser.parse_args(["--help"])
        except SystemExit as exit_:
            code = exit_.code
    if code not in (0, None):
        problems.append(f"{path}: --help exited {code}")
    if not _has_description(out.getvalue()):
        problems.append(f"{path}: no description between the usage and the arguments")
    actions: list[Any] = list(parser._actions)  # noqa: SLF001
    problems.extend(
        f"{path}: {'/'.join(a.option_strings) or a.dest} has no help"
        for a in actions
        if not isinstance(a, argparse._SubParsersAction) and a.help is None  # noqa: SLF001
    )
    for action in actions:
        if not isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            continue
        listed = {a.dest: a.help for a in action._choices_actions}  # noqa: SLF001
        for name, child in action.choices.items():
            if not listed.get(name):
                problems.append(f"{path}: {name} is missing from the listing (add help= to add_parser)")
            _walk(child, f"{path} {name}", problems)


def _has_description(text: str) -> bool:
    """Whether a paragraph that is not a section header follows the usage paragraph."""
    blocks = [b for b in text.split("\n\n") if b.strip()]
    if len(blocks) < 2:
        return False
    first_line = blocks[1].lstrip("\n").splitlines()[0]
    return not (first_line == first_line.lstrip() and first_line.endswith(":"))
