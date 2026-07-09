# 0003 — The ontology lives as flat files in the shelf, not as a2kay EntityTypes

- **Status:** decided (2026-07-08)
- **Expires:** 2027-01-08 (re-justify at the half-year)
- **Track:** governance / topology
- **Distilled into:** N/A — self-enforcing via tests/test_catalog_projection.py

## The fork

The shelf's own metadata — the **catalog** (one manifest per `MicroSoftware` instance), the **ledger**
(the append-only fitness record), and the ontology's other instance data — has to be modelled *somehow*.
Two candidates were live (exploration §6.3):

- **A — a2kay EntityTypes.** Model the catalog/ledger as entities inside a2kay's knowledge graph and let
  a2kay's engine hold the shelf's ontology.
- **B — flat files in the shelf.** One file per instance, in this repo, versioned by git like everything else.

## Decision: **B — flat files in the shelf.**

This is not a close call; two standing decisions already force it:

- **The one invariant** (`README.md`, `tests/test_boundary.py`): *a shelf package never imports a
  consumer app.* a2kay **is** a consumer (resolution 0001, "a2kay is just another consumer"). Modelling
  the shelf's ontology as a2kay EntityTypes would make the shelf **depend on a2kay** to describe itself —
  a direct inversion of the dependency arrow. The invariant kills option A on contact.
- **Resolution 0002** ("forget about Kay"): the shelf is the single self-contained home of its own model;
  Kay/a2kay is not a runtime dependency. Option A would re-introduce exactly the coupling 0002 removed.

So the ontology is **plain files under version control**, consistent with constitution I (files are the
unit of truth) and II (one concept per file, parallel-safe additive writes).

## Hard rules

- **Types in `glossary.md`, instances in `catalog/` + `ledger/`.** The glossary defines `MicroSoftware`,
  `Contract`, `LedgerEntry` (the *types*); a package's manifest and its ledger rows are the *instances*.
  The glossary's litmus holds: "would this survive deleting every package?" — no → it is instance data,
  never the glossary.
- **Every rollup is DERIVED (constitution I).** Any catalog index / ledger summary is *projected* from
  the per-instance files by a generator (`tools/catalog.py`, `make catalog`), never hand-maintained. The
  files are truth; a freshness test fails if a README drifts.
- **Supply and demand are separate files.** A `catalog/<sw>.toml` is the supply (the piece). A consumer's
  dependency is its own `use-cases/<consumer>--<sw>.toml` — the consumer *publishes* why it needs the
  piece and what surface it relies on. A manifest therefore carries **no consumer list**: that would be a
  shared, merge-prone field. Consumers are *derived* from the active use-cases (Article II — each consumer
  adds its own file, parallel-safe). A piece with zero active use-cases is **orphaned** (Article VIII).
  This instantiates the glossary's `UseCase`/`Requester`/`Owner` (the two hats: Owner controls shape,
  Requester controls retirement).
- **No engine dependency.** Reading or writing the ontology requires nothing but a text editor and git.
  A future tool may *project* it richly, but the substrate stays plain files.

## Consequence (this resolution triggers work, unlike a pure belief)

Instantiate the flat-file ontology now and **evaluate it in use** (per the "do it properly, then judge how
well it helps" directive): `catalog/` manifests for the 4 bootstrapped packages, `ledger/` entries for
their deliveries and a2kay's adopt-verdicts, and a tiny derived projection. If the flat-file model proves
too thin in practice, that is a *new* fork to reopen here — not a silent drift back toward option A, which
the invariant forbids regardless.
