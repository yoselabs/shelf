---
id: 0022
title: Every exception to a blueprint rule is justified
statement: An override or ignored path in blueprint.toml needs a reason and either an expires date or an adr naming the accepted ADR that records the durable decision; the gate reports one without.
concerns: [gate]
status: accepted
decided_by: owner
updated: 2026-10-11
distilled_into: blueprint profile.justification_problem; runner problems; templates/agents/gate.md
---

# 0022 — Every exception to a blueprint rule is justified

## Decision

- Each `[[override]]` and each `[[profile.ignore]]` entry in `docs/blueprint/blueprint.toml` has a non-empty
  `reason` and exactly one kind of life:
  - `expires = <date>`: temporary; it stops counting on that date.
  - `adr = "NNNN"`: durable; it names an accepted ADR in `docs/adr/` that records the decision (lifesim: no CI,
    builds on the owner's machines, expressed as an adr-backed override of `gate.ci`). No expiry.
- An exception with no reason, with neither field, or naming an ADR that is missing or not accepted is a problem
  the gate reports (exit 1). It counts for nothing until fixed.
- A trait such as `no-ci` is not a separate mechanism: the exception stays an override of the rows it concerns.

Why: a permanent owner decision modelled as an expiring override turns red on a date for no reason; an
exception with no recorded reason cannot be challenged later.

## Rejected

- A `[profile] traits = ["no-ci"]` that switches rows off: a second exception mechanism, with its own rules.
- An override that never expires and needs no reason: the exception outlives anyone who knows why.

## History

- 2026-10-11: decided (shelf-bif, generalised by the owner from the no-CI case to every exception).
