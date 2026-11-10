# Verification

Base: `origin/main` 5e4a4a2, whose `packages/beads-client` is identical to tag `beads-client-v0.1.0` (3afd60d).
Before the source change the new test module could not import `ReadyReadClient` or `ready_read_contract` (absent at
the base). The contract has teeth: run against deliberately wrong fakes it rejects id-sorted order, a swallowed
failure returned as `[]` (the malformed case) and an ignored label filter.

`tests/test_ready_read.py`: 8 passed (the shared contract against `Bd` over a controlled Runner and against the fake,
plus fake-only label journal, snapshot isolation, unknown/duplicate ready IDs, show faults not hiding a ready record,
and a persistent whole-read fault). Package run: 121 passed. `just check` green on this tree (lint and spelling of the
changed files, strict pyrefly, import-linter, deptry and `uv lock --check`, and the affected tests, which are all of
them because `uv.lock` changed). Not run: `just check-all` (before the tag) and a live `bd ready --label` capture; the
empty-output behaviour rests on the existing `test_list_and_ready_empty_output_is_no_rows`.
