# shelf glossary — the ontology

The canonical vocabulary of the shelf. Every concept has **exactly one** name, defined in terms of
the one above it — a chain, not a bag. (Modelled on a2kay's glossary.)

**The strict boundary — this is what keeps the glossary from growing forever:**

> The glossary defines **TYPES**. The catalog holds **INSTANCES**.
> Litmus: *"Would this entry still exist if we deleted every single package?"*
> **YES → glossary** (a concept). **NO → it names a specific piece → the catalog/manifest, never here.**

So `anyllm` never appears in this file; `MicroSoftware` and `Capability` do. The glossary is bounded
by the size of the ontology (~15 concepts, fixed), never by the size of the shelf.

---

## The spine

```
Shelf ─ the repo; the corpus of shared software pieces               (a2kay analogue: Vault)
  └─ MicroSoftware ─ one reusable, ownable unit                       dir = identity
       ├─ Kind ─ primitive | any-lib | composite | cli | framework | config-preset
       ├─ Tier ─ T0 primitive · T1 any-* · T2 composite               (T3 Product is OUT — the apps)
       ├─ Release ─ a git tag; the version                            "anyllm-v0.2.0"
       └─ provides ▸ Capability ─ the stable "stop-caring" promise    what an app no longer must care about
             ├─ realized-by ▸ Implementation ─ ours | third-party | hybrid-adapter   ← SWAPPABLE
             ├─ guaranteed-by ▸ Contract ─ durable I/O promise + invariants          ← the GENE (own file)
             │     ├─ bound-to ▸ Shape ─ current surface (names, signatures)          ← phenotype; flexible | pinned
             │     ├─ verified-by ▸ AcceptanceScenario ─ visible executable test
             │     └─ verified-by ▸ HoldoutScenario ─ hidden test in the CONSUMER repo, vs the published artifact
             └─ satisfies ▸ UseCase ─ a concrete demand: why THIS consumer needs it   ← own file
                   ├─ requested-by ▸ Consumer ─ an app (edge = its pyproject git-pin)
                   ├─ sponsored-by ▸ Sponsor ─ the accountable human (named)
                   ├─ owned-by ▸ Owner ─ controls SHAPE (CODEOWNERS)
                   └─ retired-by ▸ Requester ─ controls RETIREMENT (the two hats)

  Lifecycle (state):  candidate → active → deprecated → retired       (+ orphaned)
  Lineage (arcs):     renamed-from ▸ · absorbed-into ▸ · merged-with ▸ · supersedes ▸
  LedgerEntry ─ append-only: request → delivery → verdict → cost      (R154 fitness record; later)
```

## Load-bearing distinctions

- **Contract vs Shape.** The Contract is the durable promise (the gene); the Shape is the current
  surface (the phenotype). A `flexible` Shape may change (rename, arg→struct) while the Contract holds
  via a one-line binding + a facade. A `pinned` Shape *is* the contract (only when the value is
  serialized, passed verbatim to a third library, or on a hot path) — changing it is a major bump.
- **Implementation is not the MicroSoftware.** A MicroSoftware is "a Contract + whichever
  Implementation currently wins its tests." Our own code and a qualifying third-party dependency are
  interchangeable Implementations; the winning end-state is often a thin adapter over a dep.
- **Owner vs Requester (two hats).** Owner controls Shape and may churn it freely. Requester controls
  Retirement and a use case may not be silently deleted while a Consumer still depends on it.
