# The shelf constitution

Small on purpose. A constitution that grows long is already failing. Nine articles.

Seeded from a2kay's AGENTS.md (whole-codebase Definition of Done, no carve-outs), its glossary
discipline (one canonical name per concept), the primitive-shelf rule-of-three, and R154's factory
doctrine (contract = the unit of selection; the ledger = the fitness record).

---

### I. Files are the unit of truth; every index/catalog is DERIVED, never hand-edited.
Projecting the index (the way a2kay projects Vault → Graph, and Kay projects memory files → MEMORY.md)
removes the shared mutable surface that causes merge conflicts. If you are hand-editing a list that
many things append to, you have found a bug in the design, not a chore.

### II. One concept, one owner, one file; collaborators are injected.
Each use case, contract or primitive is one file, so two agents working in parallel touch disjoint files
*by design*: each ADDS a file and git merges disjoint adds cleanly. No locks, no coordination.
Before code goes anywhere, name its concern and its owner. Behaviour lives in a class or module that owns
it; callers hold an instance and use its methods, never its internals (process ids, file layouts, tool or
harness names). A caller that must know how has found a missing boundary (Article IV). One owner per resource lifetime: a pipe, lock or process is closed only by its owner, after every user of it has
finished; a close under a reader is a defect, not a race to tune. Collaborators
arrive as instances passed in at the edge: no module-level I/O, no global state, no constructing a
collaborator inside the code that uses it.

### III. Leave it smaller; one way only.
Shared coordination surfaces (indexes, ledgers, catalogs) take *additive, one-concept-per-file* writes
(Articles I–II): a concurrency tactic, **not** a license to let code pile up. In the code the default is
the opposite: remove dead lines, collapse duplication, delete the unused, every time you build.
Accumulation without consolidation is drift. Hard opinions, a breach is a defect, not a trade-off:
- **No optionality.** One behaviour per concern: no flags, modes or config switches that choose between
  behaviours. A real variant is a separate type behind an injected interface. An exception is a named,
  justified row ([ADR 0022](adr/0022-every-exception-is-justified.md)), never a flag.
- **No backward compatibility in code.** No shims, aliases, deprecated paths or dual code paths (the
  catalog's `deprecated` state, Article VIII, is a lifecycle label, not a code path). A breaking change
  bumps the package tag; consumers move or stay pinned (tags are never deleted).
- **Breaking is free; only the right shape costs.** Shelf is not afraid of breaking things. A change that makes a
  caller fail (a new exception to handle, a required argument, a removed name) is fine, because the failure is loud
  and a caller moves in minutes. Never keep a wrong shape to spare a caller, and never add a flag, alias or silent
  fallback so that nothing breaks. The only question is what the right shape is. No migration documents: the
  package CHANGELOG line (one per contract change) is all the upgrader needs, and it reads the new version.
  This covers stored data too: a cache key, a file format or a hash may change when the right shape needs it, and
  the cache is rebuilt. Never freeze a wrong algorithm to protect old entries; batch such changes into one release
  so a store is rebuilt once. We care about consumers by knowing better for them, and by making them evolve fast.
- **A small surface.** A public name, parameter or option costs tokens for every AI that learns it. Add one only for a
  different thing; prefer one idempotent verb (`ensure`: no-op when already so, a typed conflict when it differs) and a typed
  exception to a verb-plus-flag matrix.
- **No silent failures.** Never swallow an exception. Handle it where the caller can act on it, or let it raise.
  A failed cleanup or shutdown is reported, and the stop it belonged to still happens: a failure to record never
  leaves a worker running.
- **Tolerance is a handler, not a flag.** `missing_ok=`, `ignore_errors=`, `force=`, `overwrite=` and kin do not
  exist. The call raises a typed exception, and the caller that tolerates it catches that exception. Two actions
  that differ in kind (create versus replace) are two verbs. A `Literal` or enum parameter is the same flag in a
  different coat. ADR 0030 records the 28 old exceptions as debt to convert, not as precedent.
- **No redundancy.** One implementation of a behaviour per repo. A duplicate is allowed only as a recorded
  task that reconciliation (Article VIII) must resolve, never as the end state.
Each rule names its check; where the check does not exist yet, adopting the rule includes filing it:

| Rule | Check | State |
|---|---|---|
| Injection (II) | module-level I/O and global-state fitness test | task shelf-ufmg |
| No optionality | `tests/test_arch_bool_modes.py` bool-with-default parameters, keyword-only included, one reasoned allowlist row per current hit | blocking; extends task shelf-cypc |
| One dispatch on the OS (III) | `tests/test_arch_platform_sites.py` platform reads only in allowlisted modules | blocking |
| One value, no output-shape flags (IX) | `tests/test_arch_output_shape_flags.py` flag parameters that select the return shape | blocking |
| Async hygiene (III) | ruff `ASYNC` repo-wide (blocking calls inside `async def`) and `tests/test_arch_threads.py` hand-made threads only in reasoned files | blocking |
| One CLI home (III) | `tests/test_arch_cli_surfaces.py` `import argparse` only in verb-cli, argparse-mcp, `__main__` modules and reasoned files | blocking |
| No backward compatibility | shim / legacy / compat ban | task shelf-au97 |
| No silent failures | planted-violation test for a swallowed exception (effects research, task shelf-tyld.22) | task |
| Tolerance is a handler | bool-mode test extended to `Literal` policy parameters; the 28 C rows converted | task |
| No redundancy | `tests/test_arch_rules.py` body-duplication tests, within and across packages | blocking |
| Size limit (IV) | `tests/test_size_caps.py` file and function SLOC caps | blocking on changed files |

### IV. Size is a hard limit for code; structure is the cure.
Code files stay under a per-repo line limit (set in the repo's linter, no exceptions list, no ratchet file).
A file over the limit is a **smoke alarm**, not progress, that a boundary is missing: find it and split along it.
The limit yields only where code cannot comply, and data files (YAML, XML, JSON, generated output) are
outside it. A split made only to dodge the limit is the wrong abstraction: redesign instead.

### V. Protection is EARNED.
A contract is born `candidate` (inert — it cannot block a refactor). It becomes `active`/protected
ONLY when a live consumer demonstrably breaks without it. Protecting on fear calcifies the API and
freezes the evolution the shelf exists to enable. Protection is budgeted and expiring.

### VI. Adopt conservatively — reach for the shelf first, pull only if DEEP · STABLE · WINS.
*Pulling a shelf dep into a consumer* is the cautious act. Every time code is written, grep the shelf first (a local copy of generic substrate is redundancy, Article III); adopt an existing piece
only if it hides real complexity (deep, not a restatement), has a settled API, and wins the
weight-vs-saved trade. Any gate fails → do not adopt; the local code stays the single implementation (never
a second copy beside a shelf piece that serves the same behaviour: evolve that piece instead, Article III). If the shelf *lacks* the piece and it is generic substrate, don't just duplicate — **promote
it** (Article VII).

### VII. Promote aggressively — capitalize generic substrate at writing time; reconcile later.
The opposite posture from adopt (ADR 0006). The moment you write a generic helper, a pattern +
its safety wrapper, or an abstraction over an awkward stdlib/library API, home it in the shelf **then** —
a self-assessed "this feels reusable" is enough; **no second consumer required**. The aim is that every
app is mostly *business logic + dependencies*. Two guards, not a gate: it must be **shape-proven, not
shape-guessed** (the interface is validated by real use — the *consumer* may be future, the *shape* may
not be a guess), and it is answerable at **reconciliation** (Article VIII).

**Three triggers, not two.** Substrate glue you are about to write; a *sharp edge* discovered while
debugging (ADR 0012); and — the quietest — a dependency that is correct, documented and
correctly used, which was simply **verbose** (ADR 0015). "Stop caring about X" includes how
much you must type to use X. When that third one fires, extract the **thing** the domain has (a type
owning its own state and derivations), not a drawer of functions over the library's type; wrap, do
not inherit; and name it `any-<domain>` — the domain, never the origin library. Many methods on one
coherent subject is growth, not the accretion Article III forbids.

At a **seam** (substrate that looks like shelf material) there are **four directions**, not one verdict:
**adopt** (a piece fits), **evolve** (a piece *almost* fits → grow its contract to serve both cases —
one evolving piece beats two similar ones, when it stays coherent), **promote** (nothing covers it →
capitalize), **keep local** (yours is too niche for the shelf; never generic substrate, Article III). Aggressive promote + conservative adopt is self-correcting.

### VIII. Decay and reconciliation are mandatory.
Every piece carries a TTL; unreused past it → deprecate → retire. And a recurring **reconciliation** pass
adjudicates the aggressively-promoted catalog *with hindsight* — **merge** overlaps, **split** a
kitchen-sink, **delete** the unused, **demote back** to its one consumer (no copy left on the shelf) an over-promotion (lineage arcs record
it). This is where "was that the right abstraction?" is answered. Deletion is a virtue; a smaller shelf is
a healthier one. Neglect reconciliation and aggressive promotion rots the catalog — it is the load-bearing
other half, not optional garnish.

### IX. One complete value, compact views; the easy path is the right path.
**⚠️ Founding rule. No exceptions, no "just this once".** The philosophy is in [doctrine.md](doctrine.md); this is
its law.
- **One value, one file.** A package returns and stores one lossless value holding everything it knows. Never
  split one result across files by concern (a transcript file plus a diarization file), and never ship a summary
  in place of the data.
- **Views are pure functions on the value**, not flags that change what is computed (Article III). The default
  view serves the most common reader; narrower and wider views are other functions.
- **Cost makes it opt-in, nothing else does.** A capability that needs a second model or an external call is
  asked for; free data is always kept.
- **The pit of success.** The default is safe and correct; misuse fails loud; a missing dependency raises, never
  silently falls back.
Check: the package's README names its value, its default view and its opt-ins; a review rejects a flag that
selects an output shape. State: task to be filed as a check beside the table in Article III.
