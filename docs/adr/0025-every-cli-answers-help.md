---
id: 0025
title: every command answers --help and refuses what it does not know
statement: Every command and script answers `--help` with its usage and changes nothing, refuses an unknown flag, and acts only on the action given; built on a CLI library.
concerns: [stack, gate]
status: accepted
decided_by: owner
updated: 2026-10-12
distilled_into: blueprint stack.python-uv.cli-parse and stack.python-uv.cli-help-tested (concerns/cli_parse.py); templates/agents/python.md
---

# 0025 — every command answers --help and refuses what it does not know

## Decision

A CLI is how agents use software, so its surface is a contract:

- `<command> --help` and `<command> <sub> --help` print the usage and exit 0. They start nothing, write nothing and
  commit nothing.
- An unknown flag or argument is refused (exit 2, a message naming it). It is never dropped and never run past.
- A command does only what it was asked. It does not start a server, write a file or commit on startup unless that is
  the action given.
- The CLI is built on a library that gives this by default (argparse with `parse_args` and `add_help` kept, click,
  Typer). A hand-rolled parser, `parse_known_args`, or `add_help=False` is a bug. The one allowed shape is a two-stage
  pre-parser for global flags whose rest goes to a parser that keeps `--help`, recorded as an override of
  `stack.python-uv.cli-parse` scoped to its file (ADR 0026).
- A script run directly (`uv run tools/x.py`, a `__main__` block that parses arguments) counts as a command: it
  answers `--help` too, so an agent can read what it does before running it.
- Every command and subcommand has a description, and every flag and positional has help text. With argparse,
  `add_subparsers().add_parser(name)` with `help=None` (the default) leaves that subcommand out of the parent's
  listing, so it looks absent; give `add_parser` both `help=` (the listing line) and `description=` (the body of its
  own `--help`). A parameter with no stated purpose still shows a type label.
- Each console script has a test that runs it with `--help` (exit 0, usage printed, nothing changed) and with an
  unknown flag (refused).

A test walks the whole tree (`verb_cli.testing.assert_help_tree`): exit 0, a description between usage and
arguments, no option or positional without help, every leaf command listed with text.

Exceptions, named per repo with a reason: programs without a command line (a Windows GUI app, a Unity or Godot game).

Why: a2kay 2026-10, `serve --help` started a server that committed to main, because its parser dropped flags it
did not know; five sibling commands had the same shape, and strict parsing then caught `serve` dropping the global
`--instance`. homelab's deploy entry point refused `--help` instead of answering it. An agent probes a command with
`--help` before using it; a probe must be safe.

## Rejected

- A written rule only (shelf-2gv): the pattern came back in five more commands the next day.
- ruff banned-api on `parse_known_args`: it matches imports, not a method called on an instance (tried 2026-10-12).
- Blueprint running each command with `--help` itself: it would run the repo's code against the repo, the exact
  incident; the repo's own test runs it in a sandbox it controls.

## History

- 2026-10-12: a2kay-1k99 (`serve --help` started a server); shelf-2gv wrote the rule into python.md.
- 2026-10-12: second sighting (five owner commands); shelf-s2w made it the cli-parse row with a `# lenient:` waiver.
- 2026-10-12: amended by ADR 0026: scripts run directly are commands too, and the `# lenient:` comment becomes an
  override in blueprint.toml.
- 2026-10-12: accepted by the owner as a rule for every CLI ("every CLI should have --help"; a command that starts or
  mutates on its own is a bug), homelab's refusing parser included; the waiver narrowed to a pre-parser, and the
  cli-help-tested row added.
- 2026-10-12: a2kay 3fafcbf found the `help=None` subparser trap (argparse omits it from its parent's listing);
  amended with the description rule, and shelf-knp lifted a2kay's tree walk into `verb_cli.testing` and made
  verb-cli show a type label for a parameter with no description.
