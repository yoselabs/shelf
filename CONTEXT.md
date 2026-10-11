# shelf glossary — the ontology (CONTEXT.md)

The canonical vocabulary of the shelf. Every concept has **exactly one** name, defined in terms of
the one above it — a chain, not a bag. (Modelled on a2kay's glossary.)

**The strict boundary — this is what keeps the glossary from growing forever:**

> The glossary defines **TYPES**. The catalog holds **INSTANCES**.
> Litmus: *"Would this entry still exist if we deleted every single package?"*
> **YES → glossary** (a concept). **NO → it names a specific piece → the catalog/manifest, never here.**

So `anyllm` never appears in this file; `MicroSoftware` and `Capability` do. The glossary is bounded
by the size of the ontology (~15 concepts, fixed), never by the size of the shelf.

---

## Terms

One entry per term: a one-line definition, `_Avoid_:` names where a near-synonym is a different thing.

- **Shelf**: the repo; the corpus of shared software pieces.
- **MicroSoftware**: one reusable, ownable unit; its directory is its identity.
  _Avoid_: Implementation (a MicroSoftware is a Contract plus whichever Implementation currently wins its tests).
- **Kind**: what sort of MicroSoftware it is: primitive, any-lib, composite, cli, framework, config-preset or skill.
- **Tier**: T0 primitive, T1 any-*, T2 composite; T3 Product is out of the shelf (the apps).
- **Release**: a tag in the repo, namespaced per package (`anyllm-v0.2.0`); the version.
- **Capability**: the stable "stop-caring" promise a MicroSoftware provides; what an app no longer must care about.
- **Implementation**: ours, third-party or hybrid-adapter code that realizes a Capability; swappable.
  _Avoid_: backend (the count of Implementations is a detail the `any-` name promises you stop tracking).
- **Contract**: the durable input/output promise plus invariants; the gene, in its own file.
  _Avoid_: Shape (the current surface, not the promise).
- **Shape**: the current surface (names, signatures) a Contract is bound to; `flexible` or `pinned`.
- **AcceptanceScenario**: a visible executable test that verifies a Contract.
- **HoldoutScenario**: a hidden test in the consumer repo, run against the published artifact.
- **UseCase**: a concrete demand, in its own file: why this Consumer needs this Capability.
- **Consumer**: an app that depends on a MicroSoftware; the edge is its pyproject pin.
- **Sponsor**: the accountable human for a UseCase (named).
- **Owner**: controls the Shape (CODEOWNERS); may churn it freely.
  _Avoid_: Requester (the other hat: controls retirement).
- **Requester**: controls retirement; a use case may not be silently deleted while a Consumer still depends on it.
- **Lifecycle**: candidate, active, deprecated, retired, plus orphaned (no active use case).
- **Lineage**: arcs between pieces: renamed-from, absorbed-into, merged-with, supersedes.
- **LedgerEntry**: an append-only record of request, delivery, verdict and cost; the fitness record.
- **any-\***: a domain promise: the consumer stops caring about a whole domain, however many Implementations sit underneath.
  _Avoid_: backend-swap (the narrower reading; an ergonomic surface over one library earns the prefix too, ADR 0015).

---

## The spine

```
Shelf ─ the repo; the corpus of shared software pieces               (a2kay analogue: Vault)
  └─ MicroSoftware ─ one reusable, ownable unit                       dir = identity
       ├─ Kind ─ primitive | any-lib | composite | cli | framework | config-preset | skill
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
- **`any-*` is a domain promise, not a backend-swap promise.** The prefix means the consumer stops
  caring about a whole domain. Several interchangeable Implementations is the most visible way to
  earn it (`anyllm`), and an *ergonomic* surface over exactly one library earns it too (ADR
  0015) — the count of implementations is itself a detail the name promises the consumer will stop
  tracking. Fusing several libraries to take the better half of each is `composite`, not `any-lib`.
- **A Capability may be a thing, not a verb.** Where a domain has a noun — a document, a connection,
  an archive — the Shape is a type the consumer holds, owning its lazy reading and its derived
  values. A module of free functions that each take a third-party type as argument 1 is the
  bag-of-functions shape: the domain's thing was never extracted (`RECONCILE` step 3).
- **Owner vs Requester (two hats).** Owner controls Shape and may churn it freely. Requester controls
  Retirement and a use case may not be silently deleted while a Consumer still depends on it.
