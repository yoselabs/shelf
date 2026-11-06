## Why

Blueprint W2 (shelf-fkx.2): a checkpoint nobody has seen fail, or pass, is a checkpoint nobody tests. The suite must show every registered check and every tool role of the shipped profiles in both directions.

## What changes

- `tools/blueprint_fitness.py`, a pytest plugin registered in the root `conftest.py`: records (checkpoint id, verdict) from every `blueprint.runner` evaluation before overrides, in every xdist process; after a green run of the whole `packages/blueprint/tests` suite it fails the session for each required checkpoint not seen passing and not seen failing or not set up.
- `packages/blueprint/tests/known_gaps.toml`: today's uncovered directions, each naming a bead (shelf-fkx.11). A gap the suite now covers must be deleted, so the list only shrinks.
- Partial runs (`-k`, a node id, a missing test file) assert nothing.

## Not yet

Closing the 57 gaps with scenarios (shelf-fkx.11).
