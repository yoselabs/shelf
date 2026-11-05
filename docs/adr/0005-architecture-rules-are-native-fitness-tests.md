---
id: 0005
title: Architecture rules run in the toolchain; AST facts are native tests
statement: Import-graph rules run in-toolchain (import-linter in pyproject; ruff TID251 for banned APIs); AST-fact rules stay pure-stdlib pytest, body duplication blocking across packages too; no policy engine.
concerns: [gate, tooling]
status: accepted
decided_by: owner
updated: 2026-11-05
expires: 2027-01-08
distilled_into: blueprint python-uv architecture role; tests/test_arch_rules.py for the AST facts
---

# 0005 — Architecture rules run in the toolchain; AST facts are native tests, not OPA/Rego

## Decision

Two classes of rule, two enforcers:

- **Import graph** (layers, dependency direction, cycles, the one invariant, undeclared sibling edges):
  **import-linter** contracts in `[tool.importlinter]` in `pyproject.toml`, run by `just arch`. A guard
  test keeps `root_packages` equal to `packages/*/src` and the `independence` ignore list equal to the
  workspace dependencies the packages declare.
- **Banned APIs** (a consumer app in a package's tests, a clock or `uuid4` in a core): ruff `TID251`
  banned-api, one `msg` per entry, run by `just lint`.
- **AST facts** (RG001-RG004, below): stay native, pure-stdlib pytest.

The line is "no non-hermetic binary, no policy engine". A pip dev-dependency that parses imports is on the
right side of it; OPA is not. Benched 2026-10-11 on the shelf, a2kay and a2web.

### AST-fact rules

a2kit's architectural rules (RG001 body-duplication, RG002 private-name-collision, RG003
allowlist-hygiene, RG004 dependency-upper-bounds) are reimplemented by *intent* as native Python
fitness tests, walk the AST
(`ast`), read the manifests (`tomllib`), pure stdlib, inside `just check`, ownable, deletable.

**Scope rule** (load-bearing, departs from a2kit). a2kit was one package, the shelf is many independent ones:

- **Within a package:** duplication or name collision is a bug. **Blocking** (`tests/test_arch_rules.py`).
- **Across packages:** body duplication is **blocking** too (Article III: one implementation per repo), with
  no allowlist; lift the body to one package or file a task. A private name shared by two packages is not
  checked: the same name over different bodies is not redundancy (the advisory report flagged only those).
- **Dependency upper bounds:** always blocking; an unbounded dep breaks silently on a major bump
  (ADR 0001's ethos). Exceptions go in `tests/arch_allowlist.toml` **with a reason** (RG003).

Built: `tools/arch_rules.py` (engine: alpha-equivalence body hashing with local names and literals
abstracted but call targets/attributes kept for precision; private-name and dep-bound extractors;
allowlist loader), the blocking rules, the allowlist, and upper bounds
on package deps (`torch<3`, `docling<3`, ...); `html2text` is allowlisted (date-versioned upstream, no
semver bound is meaningful).

The build-vs-adopt gate (constitution VI) thereby has executable architectural teeth. If a rule ever
needs cross-repo fact-sharing only a policy engine can give, that is a new fork to reopen here.

## Rejected

- **B: a hand-written import DAG in pytest.** It re-implements grimp and has no exhaustiveness.
- **C: tach.** Blind to cross-package imports in a uv workspace, no exhaustiveness.

- **A: migrate as Rego** (vendor the `.rego` bundle + `extract_facts.py`, add OPA). OPA is a
  non-hermetic binary substrate, the scar tissue the shelf exists to shed (R154, constitution VI,
  ADR 0004): every consumer and CI would need `brew install opa`, and fact extraction is a second
  parallel toolchain. The rules' worth is their intent, not their Rego-ness; native also gives finer
  control of *scope*, which OPA could not express cleanly here.

## History

- 2026-07-08: decided. Expires 2027-01-08. Track: tooling / architecture fitness.
- 2026-10-11: amended (shelf-435). The 2026-07-08 text was written for a2kit's four AST-fact rules and was read as
  covering the import DAG too. The bench on shelf, a2kay and a2web chose import-linter and TID251; tach was refused.
  `tests/test_boundary.py` retired in favour of the `forbidden` contract. AST rules, scope rule, allowlist and expiry unchanged.
- 2026-11-05: amended. Article III makes redundancy a defect, so cross-package body duplication blocks and
  `just advisory` / `tools/arch_advisory.py` are removed. Zero cross-package body duplicates existed; the
  advisory's findings were all private-name collisions, which are no longer checked across packages.
