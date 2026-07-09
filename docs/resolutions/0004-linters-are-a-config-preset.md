# 0004 — The linter setup is a config-preset consumers inherit, not a CLI

- **Status:** decided (2026-07-08)
- **Expires:** 2027-01-08 (re-justify at the half-year)
- **Track:** tooling / how-things-are-done
- **Distilled into:** N/A — self-enforcing via docs/linting.md + Makefile

## The fork

The shelf's quality bar has to reach consumers somehow. Two shapes (exploration §6.5):

- **A — a CLI.** Ship `shelf-lint` (or `a2lint`-style): consumers `pip install` it and run one command.
- **B — a config-preset.** The shelf's `pyproject` `[tool.*]` blocks + `Makefile` targets ARE the
  reference; a consumer inherits by **copying** them and owning the copy.

## Decision: **B — a config-preset.**

- **A CLI is new substrate to care about** — the exact scar tissue the shelf exists to shed (R154,
  constitution VI). It hides the config, pins the consumer to our release cadence, and makes "eject"
  hard. A wrapper CLI over ruff/ty is a deep-module *anti*-pattern: it adds a layer that earns nothing.
- **A config-preset is ownable.** The consumer sees every rule, overrides any of them, and can walk away
  with a plain `pyproject`. That is the shelf's whole ethos: *inherit the judgment, own the result.*
- **The toolchain is already declarative.** ruff, ty, codespell, deptry, coverage are all configured in
  `pyproject.toml` + driven by `make`. There is nothing a CLI would add except indirection.

So this repo's own linting **is** the reference (`pyproject.toml` `[tool.ruff|codespell|coverage]`,
per-package `[tool.deptry]`, and the `Makefile` gate). See `docs/linting.md` for the full toolchain and
the inheritance procedure.

## Distribution = copy, not dependency

- **A consumer copies the blocks on onboarding** (documented in `consuming-the-shelf.md`). The copy is
  theirs — constitution VI (duplication is cheaper than the wrong abstraction) applies to config too.
- **No runtime dependency.** ruff cannot `extend` from an installed package anyway; and a config a
  consumer cannot edit is a cage, not a preset. Copy keeps the consumer sovereign.
- **Drift is acceptable and visible.** A consumer that diverges has made a local choice, on purpose. The
  shelf is the reference to *converge back toward*, not a lock.

## What "config-preset" means in the ontology

This is the first instance of the `config-preset` **Kind** (glossary: `MicroSoftware.Kind`). It provides
one Capability — *"stop re-litigating how this repo is linted"* — and its Implementation is a set of
`pyproject`/`Makefile` fragments rather than importable code. Its contract is behavioural (the gate is
green ⇒ the code meets the bar), verified by `make check` itself.

## Note — the AST/architectural rules are a *separate* decision

The a2kit-derived architectural rules (body-dup, private-name-collision, dep-upper-bound, layer-DAG,
no-`dict[str,Any]`) — currently authored in **Rego/OPA** — are NOT part of this config-preset. Whether
to migrate them as Rego (bring OPA in) or reimplement their intent as native Python fitness tests is
its own fork; see the backlog and the forthcoming resolution 0005.
