# The shelf constitution

Small on purpose. A constitution that grows long is already failing. Eight articles.

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
weight-vs-saved trade. Any gate fails → duplicate locally; duplication is cheaper than the wrong
abstraction. If the shelf *lacks* the piece and it is generic substrate, don't just duplicate — **promote
it** (Article VII).

### VII. Promote aggressively — capitalize generic substrate at writing time; reconcile later.
The opposite posture from adopt (resolution 0006). The moment you write a generic helper, a pattern +
its safety wrapper, or an abstraction over an awkward stdlib/library API, home it in the shelf **then** —
a self-assessed "this feels reusable" is enough; **no second consumer required**. The aim is that every
app is mostly *business logic + dependencies*. Two guards, not a gate: it is always **extracted, never
invented** (real code a real app needed — never an empty package to look complete), and it is answerable
at **reconciliation** (Article VIII). Aggressive promote + conservative adopt is self-correcting.

### VIII. Decay and reconciliation are mandatory.
Every piece carries a TTL; unreused past it → deprecate → retire. And a recurring **reconciliation** pass
adjudicates the aggressively-promoted catalog *with hindsight* — **merge** overlaps, **split** a
kitchen-sink, **delete** the unused, **demote / duplicate back** an over-promotion (lineage arcs record
it). This is where "was that the right abstraction?" is answered. Deletion is a virtue; a smaller shelf is
a healthier one. Neglect reconciliation and aggressive promotion rots the catalog — it is the load-bearing
other half, not optional garnish.
