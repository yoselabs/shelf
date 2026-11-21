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
  exist. A required thing that is absent raises a typed exception, and the caller that tolerates it catches that
  exception. Lookup of an optional thing is a value in the return type (below), not an exception. Convergence ("make it
  exist", "make it gone") is one idempotent verb (`ensure`). Two actions that differ in kind (create versus replace)
  are two verbs. A `Literal` or enum parameter is the same flag in a different coat. ADR 0030 records the 28 old
  exceptions as debt to convert, not as precedent.
- **Two kinds of failure** (Go's returned `error` versus `panic`). An *expected outcome* is a normal result the
  caller must branch on (a merge conflict, an absent optional thing, a refused push): a value in the return type
  (`X | None`, or a union such as `Rebased | Conflict`); never an exception, never a bool flag. The union is the
  channel only: pyrefly lets a caller narrow it but does not force a look (a discarded value is legal), so consuming it
  is a planned check: a discarded or non-exhaustively handled outcome union is a violation; consume with `match` plus
  `assert_never`. A failure the function *cannot continue from* (broken invariant, environment gone, required thing
  absent, caller misuse) is an exception, never swallowed (no `except X: pass`, no `contextlib.suppress` of a typed
  failure), handled only where something useful can be done, normally the edge. No Result type on every function:
  only where the outcome is expected.
- **Failure plumbing.**
  - *Owned thread* (a pump): a callback that raises stores the FIRST error under synchronization, is no longer
    invoked, while draining continues so the child never blocks; the owner re-raises it at shutdown, after join.
  - *Cleanup*: attempt every cleanup independently. One failure propagates unchanged; two or more raise an
    `ExceptionGroup` (`BaseExceptionGroup` when cancellation or `KeyboardInterrupt` is among them; cancellation is
    preserved, never swallowed). Async cleanup is bounded and shielded. Callers of such code use `except*`.
  - *Exceptions of a package* share ONE base class: "recognized failures of this package", not everything it can
    raise. A raw `OSError` may cross when its standard meaning stays useful. Wrap only to add domain meaning, always
    `raise X(...) from exc`, never for catch convenience.
  - *Log once, at the edge*: a library neither logs-and-swallows nor logs-and-reraises.
- **No redundancy.** One implementation of a behaviour per repo. A duplicate is allowed only as a recorded
  task that reconciliation (Article VIII) must resolve, never as the end state.
Each rule names its check; where the check does not exist yet, adopting the rule includes filing it:

| Rule | Check | State |
|---|---|---|
| Injection (II) | `tests/test_arch_module_level_state.py` import-time I/O, `global` statements and function-mutated module containers in `packages/*/src`, one exact-count reasoned row per file; the 11 `debt:` file rows (14 hits) are conversions still owed, 4 `outcome:` rows (6 hits) are documented registries; module-level instances of stateful classes are hit, a collaborator constructed inside its user is not checked to an injected collaborator | blocking |
| Decay (VIII) | `tests/test_arch_dead_public_api.py` a name in a package's `__all__` that no other package, test, use-case, config or script mentions beside the package; a hit is a deletion candidate | report only (consumers outside this repo are invisible to it) |
| README names its value, default view, opt-ins (IX) | `tests/test_arch_readme_names_its_value.py` first paragraph is prose, plus a `Default view:` and an `Opt-ins:` line ([convention](arch-rules.md#readme-convention)); every package has a `debt:` row until its README gains the lines | blocking |
| No optionality | `tests/test_arch_bool_modes.py` bool-with-default parameters, keyword-only included, one reasoned allowlist row per current hit | blocking; extends task shelf-cypc |
| One dispatch on the OS (III) | `tests/test_arch_platform_sites.py` platform reads only in allowlisted modules | blocking |
| One value, no output-shape flags (IX) | `tests/test_arch_output_shape_flags.py` flag parameters that select the return shape | blocking |
| Async hygiene (III) | ruff `ASYNC` repo-wide (blocking calls inside `async def`) and `tests/test_arch_threads.py` hand-made threads only in reasoned files | blocking |
| One CLI home (III) | `tests/test_arch_cli_surfaces.py` `import argparse` only in verb-cli, argparse-mcp, `__main__` modules and reasoned files | blocking |
| No backward compatibility | shim / legacy / compat ban | task shelf-au97 |
| No silent failures | planted-violation test for a swallowed exception (effects research, task shelf-tyld.22) | task |
| Tolerance is a handler | `tests/test_arch_bool_modes.py` public parameters named force/overwrite/missing_ok/exist_ok/ignore_errors/check, or annotated Literal/Enum (aliases included); `debt:` rows are conversions still owed | blocking |
| Two kinds of failure (III) | swallowed handlers: `tests/test_arch_swallowed_exceptions.py` silent `except` handlers and `contextlib.suppress`, one exact-count reasoned row per file; a handler that returns a typed value is not flagged; no `debt:` hits remain: every handler is an `outcome:` row | blocking |
| Outcome unions are consumed (III) | `tests/test_arch_outcome_unions_consumed.py` a call to a function whose return is a union of shelf outcome types (frozen dataclasses), used as a statement, never narrowed, or matched non-exhaustively; callees resolved by name and import map, methods only when every `def` of the name is an outcome union; the 2 `debt:` hits are fakes that drop `Offline` | blocking |
| Cancellation is not lost (III) | `tests/test_arch_cancellation_not_lost.py` `except BaseException` / `CancelledError` / `KeyboardInterrupt` / `SystemExit` / bare `except:` that does not raise on every path, one reasoned row per file | blocking |
| No error erasure (III) | `tests/test_arch_error_erasure.py` an `except` that returns `None` / `False` / `0` / `''` / an empty container and does not raise, unless it catches only absence types; `return` inside `finally`; disjoint from the swallowed-exceptions test; `debt:` rows are conversions still owed | blocking |
| No check-then-act (III) | `tests/test_arch_check_then_act.py` `exists` / `is_file` / `is_dir` / `os.access` whose answer guards a mutation of the same path expression in the same function; `outcome:` rows are lock-protected or single-owner cases | blocking |
| Bounded retry (III) | `tests/test_arch_bounded_retry.py` `while True` / `while <flag>` loop with a handler that continues and a sleep, but no attempt counter, deadline or clock read | blocking |
| Package exception base (III) | `tests/test_arch_package_exception_base.py` every exception a package defines derives from one root class of that package (convention: `<Package>Error`); one `debt:` row per package with several roots | blocking |
| Exception handled by the caller (III) | static call-graph check | refused for now: with types (pyrefly `--report-pysa`) 96.7% of calls resolve, but the shelf's 9 cross-package hits were all deliberate pass-through (docstring paperwork, 0 bugs), the check costs 114 s, and Result-everywhere contradicts ADR 0030; reopen if hits pass about 50 or another codebase shows real bugs; [research](research/checked-exceptions.md), [typed calls](research/typed-call-resolution.md) |
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
selects an output shape. State: the flag rule is blocking (`tests/test_arch_output_shape_flags.py`, row "One value, no output-shape
flags (IX)" in the Article III table). The README naming is blocking too (`tests/test_arch_readme_names_its_value.py`, convention in
[arch-rules](arch-rules.md#readme-convention)). "One value, one file" is review-only: two files for one result needs meaning a parser cannot see.
