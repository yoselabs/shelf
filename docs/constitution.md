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

### II. One concept per file — one use case, one contract, one primitive.
Two agents working in parallel must touch disjoint files *by design*. Each ADDS a file; git merges
disjoint adds cleanly. No locks, no concurrency control, no coordination.

### III. Parallel-safe coordination, not accumulation.
Shared coordination surfaces (indexes, ledgers, catalogs) take *additive, one-concept-per-file* writes
so parallel sessions never conflict (Articles I–II) — a concurrency tactic, **not** a license to let
code pile up. In the code itself the default is the opposite: **leave it smaller than you found it** —
remove dead lines, collapse duplication, delete the unused, every time you build. Accumulation without
consolidation is drift. Deletion is the virtue (Article VIII); a growing file that no one prunes is a
smoke alarm (Article IV), not progress.

### IV. Structure controls size, not caps.
A large file is a **smoke alarm** that a structural boundary is missing — a pattern un-applied, two
responsibilities fused, a list that should be files. The response is to find the missing boundary,
never to swing a line-count axe. A size signal may *trigger a design review*; it is never the law.
Arbitrary caps force arbitrary splits — the wrong abstraction, which is more expensive than a big file.

### V. Protection is EARNED.
A contract is born `candidate` (inert — it cannot block a refactor). It becomes `active`/protected
ONLY when a live consumer demonstrably breaks without it. Protecting on fear calcifies the API and
freezes the evolution the shelf exists to enable. Protection is budgeted and expiring.

### VI. Adopt conservatively — reach for the shelf first, pull only if DEEP · STABLE · WINS.
*Pulling a shelf dep into a consumer* is the cautious act. Grep the shelf first; adopt an existing piece
only if it hides real complexity (deep, not a restatement), has a settled API, and wins the
weight-vs-saved trade. Any gate fails → do not adopt; the local code stays the single implementation (never
a second copy beside a shelf piece that serves the same behaviour: evolve that piece instead, Article IX). If the shelf *lacks* the piece and it is generic substrate, don't just duplicate — **promote
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
capitalize), **keep local** (yours is too niche for the shelf; never generic substrate, Article IX). Aggressive promote + conservative adopt is self-correcting.

### VIII. Decay and reconciliation are mandatory.
Every piece carries a TTL; unreused past it → deprecate → retire. And a recurring **reconciliation** pass
adjudicates the aggressively-promoted catalog *with hindsight* — **merge** overlaps, **split** a
kitchen-sink, **delete** the unused, **demote back** to its one consumer (no copy left on the shelf) an over-promotion (lineage arcs record
it). This is where "was that the right abstraction?" is answered. Deletion is a virtue; a smaller shelf is
a healthier one. Neglect reconciliation and aggressive promotion rots the catalog — it is the load-bearing
other half, not optional garnish.

### IX. Hard opinions: one way, one owner, injected.
Everything we build, apps and shelf packages alike, obeys these. A breach is a defect, not a trade-off.
- **No optionality.** One behaviour per concern: no flags, modes or config switches that choose between
  behaviours. A real variant is a separate type behind an injected interface. An exception is a named,
  justified row ([ADR 0022](adr/0022-every-exception-is-justified.md)), never a flag.
- **No backward compatibility in code.** No shims, aliases, deprecated paths or dual code paths (the
  catalog's `deprecated` state, Article VIII, is a lifecycle label, not a code path). A breaking
  change bumps the package tag; consumers move or stay pinned (tags are never deleted, Article VIII).
- **No redundancy.** One implementation of a behaviour per repo. A duplicate is allowed only as a recorded
  task that reconciliation (Article VIII) must resolve, never as the end state. Article VI's "duplicate
  locally" is a debt, not a decision.
- **Decomposition and isolation.** Before code goes anywhere, name its concern and its owner. Behaviour
  lives in a class or module that owns it; callers hold an instance and use its methods, never its
  internals (process ids, file layouts, tool or harness names). A caller that must know how has found a
  missing boundary (Article IV).
- **Dependency injection.** Collaborators arrive as instances passed in at the edge. No module-level I/O,
  no global state, no constructing a collaborator inside the code that uses it.
- **Shelf awareness.** Every time code is written: does the shelf have it (borrow, Article VI), is it generic
  (promote, Article VII)? A local copy of generic substrate is redundancy.

Each rule names its check; where the check does not exist yet, adopting the rule includes filing it.
