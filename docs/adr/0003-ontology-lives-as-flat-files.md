---
id: 0003
title: The ontology lives as flat files
statement: The shelf's catalog, use-cases and ledger are plain files under version control, one per instance, with every rollup derived; they are never a2kay EntityTypes.
concerns: [doctrine, packaging]
status: accepted
decided_by: owner
updated: 2026-07-08
expires: 2027-01-08
distilled_into: N/A — self-enforcing via tests/test_catalog_projection.py
---

# 0003 — The ontology lives as flat files in the shelf, not as a2kay EntityTypes

## Decision

The **catalog** (one manifest per `MicroSoftware`), the **ledger** (append-only fitness record) and
the ontology's other instance data are **plain files under version control**, one file per instance.
Consistent with constitution I (files are the unit of truth) and II (one concept per file,
parallel-safe additive writes).

- **Types in `CONTEXT.md`, instances in `catalog/` + `ledger/`.** The glossary's litmus holds:
  "would this survive deleting every package?" No means instance data, never the glossary.
- **Every rollup is DERIVED (constitution I).** Catalog index and ledger summary are *projected* by a
  generator (`tools/catalog.py`, `just catalog`), never hand-maintained. A freshness test fails if a
  README drifts.
- **Supply and demand are separate files.** `catalog/<sw>.toml` is the supply. A consumer's
  dependency is its own `use-cases/<consumer>--<sw>.toml`, which publishes why it needs the piece and
  what surface it relies on. A manifest carries **no consumer list** (a shared, merge-prone field);
  consumers are *derived* from active use-cases (Article II). A piece with zero active use-cases is
  **orphaned** (Article VIII). Owner controls shape, Requester controls retirement.
- **No engine dependency.** Reading or writing the ontology needs a text editor and the VCS. A future
  tool may *project* it richly; the substrate stays plain files.

## Rejected

- **A: a2kay EntityTypes.** Not a close call; two standing decisions kill it. The one invariant
  (the import-linter `forbidden` contract in `pyproject.toml`: a shelf package never imports a consumer) plus a2kay being a consumer
  (ADR 0001) means modelling the ontology in a2kay makes the shelf depend on a2kay to describe itself.
  ADR 0002 ("forget about Kay") removed exactly that coupling.

## History

- 2026-07-08: decided. Expires 2027-01-08. Track: governance / topology. Triggered work: instantiate
  the flat-file ontology (catalog manifests for the 4 bootstrapped packages, ledger entries for their
  deliveries and a2kay's adopt-verdicts, a tiny derived projection) and judge it in use. If it proves
  too thin, that is a new fork to reopen here, never a silent drift toward option A.
