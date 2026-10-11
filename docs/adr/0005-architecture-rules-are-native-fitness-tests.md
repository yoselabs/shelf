---
id: 0005
title: Architecture rules are native Python fitness tests
statement: Architecture rules run as pure-stdlib pytest fitness tests, blocking within a package and advisory across packages; no OPA/Rego, no policy engine.
concerns: [gate, tooling]
status: accepted
decided_by: owner
updated: 2026-07-08
expires: 2027-01-08
distilled_into: N/A — self-enforcing via tests/test_arch_rules.py
---

# 0005 — Architectural rules are native Python fitness tests, not OPA/Rego

## Decision

a2kit's architectural rules (RG001 body-duplication, RG002 private-name-collision, RG003
allowlist-hygiene, RG004 dependency-upper-bounds) are reimplemented by *intent* as native Python
fitness tests, the way `tests/test_boundary.py` already enforces the one invariant: walk the AST
(`ast`), read the manifests (`tomllib`), pure stdlib, inside `make check`, ownable, deletable.

**Scope rule** (load-bearing, departs from a2kit). Constitution VI values some duplication; a2kit was
one package, the shelf is many deliberately independent ones:

- **Within a package:** duplication or name collision is a bug. **Blocking** (`tests/test_arch_rules.py`).
- **Across packages:** duplication is a *signal*, not a sin: a body shared by two packages is a
  candidate for a T0 primitive (rule of three). **Advisory only** (`make advisory`, never a build
  failure); forcing the abstraction would violate VI.
- **Dependency upper bounds:** always blocking; an unbounded dep breaks silently on a major bump
  (ADR 0001's ethos). Exceptions go in `tests/arch_allowlist.toml` **with a reason** (RG003).

Built: `tools/arch_rules.py` (engine: alpha-equivalence body hashing with local names and literals
abstracted but call targets/attributes kept for precision; private-name and dep-bound extractors;
allowlist loader), the four blocking rules, `tools/arch_advisory.py`, the allowlist, and upper bounds
on package deps (`torch<3`, `docling<3`, ...); `html2text` is allowlisted (date-versioned upstream, no
semver bound is meaningful).

The build-vs-adopt gate (constitution VI) thereby has executable architectural teeth. If a rule ever
needs cross-repo fact-sharing only a policy engine can give, that is a new fork to reopen here.

## Rejected

- **A: migrate as Rego** (vendor the `.rego` bundle + `extract_facts.py`, add OPA). OPA is a
  non-hermetic binary substrate, the scar tissue the shelf exists to shed (R154, constitution VI,
  ADR 0004): every consumer and CI would need `brew install opa`, and fact extraction is a second
  parallel toolchain. The rules' worth is their intent, not their Rego-ness; native also gives finer
  control of *scope*, which OPA could not express cleanly here.

## History

- 2026-07-08: decided. Expires 2027-01-08. Track: tooling / architecture fitness.
