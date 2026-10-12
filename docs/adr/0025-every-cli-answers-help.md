---
id: 0025
title: every command answers --help and refuses what it does not know
statement: Every CLI command answers `--help` with its usage and changes nothing; an unknown flag is refused; a command acts only on the action it was given. Built on a CLI library that does this by default.
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
  pre-parser for global flags whose rest goes to a parser that keeps `--help`, and it says so with
  `# lenient: <reason>`.
- Each console script has a test that runs it with `--help` (exit 0, usage printed, nothing changed) and with an
  unknown flag (refused).

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
- 2026-10-12: accepted by the owner as a rule for every CLI ("every CLI should have --help"; a command that starts or
  mutates on its own is a bug), homelab's refusing parser included; the waiver narrowed to a pre-parser, and the
  cli-help-tested row added.
