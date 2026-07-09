# 0005 — Architectural rules are native Python fitness tests, not OPA/Rego

- **Status:** decided (2026-07-08)
- **Expires:** 2027-01-08 (re-justify at the half-year)
- **Track:** tooling / architecture fitness
- **Distilled into:** N/A — self-enforcing via tests/test_arch_rules.py

## The fork

a2kit ships architectural rules as **Rego policies run under OPA** (`opa eval` over a
JSON fact-dump; `brew install opa`): RG001 body-duplication, RG002 private-name-collision,
RG004 dependency-upper-bounds, RG003 allowlist-hygiene. Bringing their value to the shelf, two ways:

- **A — migrate as Rego.** Vendor the `.rego` bundle + `extract_facts.py`, add OPA to the toolchain.
- **B — reimplement their *intent* as native Python fitness tests**, the way `tests/test_boundary.py`
  already enforces the one invariant.

## Decision: **B — native Python fitness tests.**

- **OPA is a non-hermetic binary substrate** — the exact scar tissue the shelf exists to shed (R154,
  constitution VI, resolution 0004). Every consumer would need `brew install opa`; CI would need it;
  the fact-extraction machinery is a second, parallel toolchain. The rules' worth is their *intent*, not
  their Rego-ness.
- **The shelf already has the pattern.** `tests/test_boundary.py` is architecture-fitness as pytest.
  These rules are the same shape: walk the AST (`ast`), read the manifests (`tomllib`) — pure stdlib,
  runs inside `make check`, ownable, deletable. No new substrate.
- **Native gives finer control** of the one thing OPA could not express cleanly here — *scope* (below).

## The scope rule (this is load-bearing, and it departs from a2kit)

Constitution VI **values some duplication** ("cheaper than the wrong abstraction"). a2kit was one package,
so "cross-file" meant "within the project." The shelf is *many deliberately-independent packages*, so:

- **Within a package** → duplication / name-collision is a bug. **Blocking** (`tests/test_arch_rules.py`).
- **Across packages** → duplication is a *signal*, not a sin: a body shared by two packages is a
  candidate for a T0 primitive (rule of three). **Advisory only** (`make advisory`), never a build
  failure. Forcing the abstraction would violate VI.
- **Dependency upper-bounds** → always blocking; an unbounded dep breaks silently on a major bump
  (resolution 0001's ethos). Exceptions go in `tests/arch_allowlist.toml` **with a reason** (RG003).

## What was built

- `tools/arch_rules.py` — the engine. Alpha-equivalence body hashing (local names + literals abstracted;
  call targets/attributes KEPT so precision stays high), private-name and dep-bound extractors, allowlist
  loader. Pure stdlib. Verified: alpha-equivalent bodies match, different call targets do not.
- `tests/test_arch_rules.py` — four blocking rules (dup, name-collision, dep-bound, allowlist-hygiene).
- `tools/arch_advisory.py` + `make advisory` — the non-blocking cross-package report.
- `tests/arch_allowlist.toml` — the reasoned suppression list (RG003 enforces a reason per entry).
- Dependency upper bounds added to the packages (`torch<3`, `docling<3`, …); `html2text` allowlisted
  (date-versioned upstream — no semver bound is meaningful).

## Consequence

The build-vs-adopt gate (constitution VI) now has *executable* architectural teeth beyond the one
invariant, and a2kit's Rego bundle is **not** a dependency — its intent lives here, in the shelf's own
idiom. If a rule ever needs cross-repo fact-sharing that only a policy engine can give, that is a new
fork to reopen here; at N=1..few packages, stdlib fitness tests are the smaller, correct instrument.
