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

### III. Append over mutate.
A new file beats editing a shared list. Prefer additive change; let derivation (Article I) reassemble.

### IV. Structure controls size, not caps.
A large file is a **smoke alarm** that a structural boundary is missing — a pattern un-applied, two
responsibilities fused, a list that should be files. The response is to find the missing boundary,
never to swing a line-count axe. A size signal may *trigger a design review*; it is never the law.
Arbitrary caps force arbitrary splits — the wrong abstraction, which is more expensive than a big file.

### V. Protection is EARNED.
A contract is born `candidate` (inert — it cannot block a refactor). It becomes `active`/protected
ONLY when a live consumer demonstrably breaks without it. Protecting on fear calcifies the API and
freezes the evolution the shelf exists to enable. Protection is budgeted and expiring.

### VI. Reach for the shelf first; adopt only if DEEP · STABLE · WINS.
Before hand-rolling a helper, grep the shelf. Adopt an existing piece only if it hides real complexity
(deep, not a restatement), has a settled API (you are not the first to stress it), and wins the
weight-vs-saved trade. Any gate fails → duplicate locally. Duplication is far cheaper than the wrong
abstraction. (The three gates pick candidates; a contract's tests adjudicate them — see the ontology.)

### VII. Promotion, not publication.
A piece enters the catalog (gets a manifest) only when a **second** consumer pulls it. Nothing is
published to look complete. This is why the 3 T0 primitives stayed in a2kay at bootstrap: n=1 there,
unearned here.

### VIII. Decay is mandatory.
Every piece carries a TTL. Unreused past it → deprecate → retire. No immortal entries. Deletion is a
virtue, not a failure; a smaller shelf is a healthier one.
