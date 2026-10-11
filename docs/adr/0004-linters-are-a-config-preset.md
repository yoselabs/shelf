---
id: 0004
title: Linters are a config-preset, not a CLI
statement: The shelf's own pyproject [tool.*] blocks and Makefile targets are the lint reference; a consumer copies them and owns the copy. No lint CLI, no runtime dependency.
concerns: [gate, tooling]
status: accepted
decided_by: owner
updated: 2026-07-08
expires: 2027-01-08
distilled_into: N/A — self-enforcing via docs/linting.md + Makefile
---

# 0004 — The linter setup is a config-preset consumers inherit, not a CLI

## Decision

This repo's own linting **is** the reference: `pyproject.toml` `[tool.ruff|codespell|coverage]`,
per-package `[tool.deptry]`, and the `Makefile` gate. A consumer inherits by **copying** those blocks
on onboarding (`consuming-the-shelf.md`) and owns the copy. Full toolchain and inheritance procedure:
`docs/linting.md`.

- **Copy, not dependency.** The copy is theirs (constitution VI: duplication is cheaper than the
  wrong abstraction, config included). ruff cannot `extend` from an installed package anyway, and a
  config a consumer cannot edit is a cage, not a preset.
- **Drift is acceptable and visible.** A consumer that diverges has made a local choice on purpose.
  The shelf is the reference to converge back toward, not a lock.
- **Ontology:** the first `config-preset` **Kind** (see `CONTEXT.md`). Its Capability is "stop
  re-litigating how this repo is linted"; its Implementation is `pyproject`/`Makefile` fragments, not
  importable code; its contract is behavioural (gate green means the code meets the bar), verified by
  `make check` itself.
- **Separate decision:** the a2kit-derived architectural rules (body-dup, private-name-collision,
  dep-upper-bound, layer-DAG, no-`dict[str,Any]`), authored in Rego/OPA, are not part of this preset;
  see ADR 0005.

## Rejected

- **A: a CLI (`shelf-lint`, `a2lint`-style, `pip install` + one command).** A CLI is new substrate to
  care about, the exact scar tissue the shelf exists to shed (R154, constitution VI). It hides the
  config, pins the consumer to our release cadence and makes eject hard. A wrapper over ruff and the
  type checker is a deep-module *anti*-pattern: a layer that earns nothing, since the toolchain (ruff,
  type checker, codespell, deptry, coverage) is already declarative in `pyproject.toml` + `make`.

## History

- 2026-07-08: decided. Expires 2027-01-08. Track: tooling / how-things-are-done.
