# beads-client

Status: **candidate**. Shape: flexible. Protection is not yet earned by a live consumer.

`Bd(actor, cwd, exe, timeout, run, lock_retries)` runs `bd --actor <actor> <args> --json` through one injectable runner.
Every failure is a `BdError(kind, text, missing_sections)`; kinds: `not_found`, `not_claimable`, `precondition`, `lint`,
`malformed`, `missing_binary`, `timeout`, `version`, `other`. Reads return frozen `Bead`/`Comment`/`Dep` records and treat a
malformed reply as a fault, never as absence. `show(id)` requires exactly one matching record (a single object or
one-element array); an empty array is malformed. Only complete issue-absence diagnostics yield `None`; database/table
failures or mixed diagnostics remain errors. The structural `TaskReadClient` exposes this existing positional read only.

Omitted optional title, description and acceptance text default to `""`; omitted dependencies default to `()`.
Present values of those text fields must be strings; present dependencies must be an array of records with nonempty
target ID (`id` or `depends_on_id`) and relationship (`dependency_type` or `type`). Supplied dependency title/status/
close reason must be strings; omitted ones default to `""`. Relationship values are preserved without an allowlist,
including `parent-child`. Unknown extra fields remain tolerated. These consumed-field rules also apply to list/ready
through the same owning record decoder; mutation commands and unrelated optional fields are unchanged.

`beads_client.testing.FakeTaskReadClient(records=(), faults=...)` supplies an independent semantic read backlog.
Seed frozen `Bead` records and map requested IDs to typed `BdError` faults; faults override records, and `not_found`
means authoritative absence. Other faults persist across reads and preserve kind, text and missing sections. `reads`
records requested IDs; record snapshots are isolated from caller mutation. No runner or mutation method is involved.
`task_read_contract(make)` checks success, empty text, dependency preservation, absence, independent backlogs and typed
read failures against both this fake and `Bd` over a controlled Runner.

`update(..., if_assignee=, if_status=)` passes bd's fences; exit 13 is
`precondition`. `claim` and `unclaim` answer whether the bead changed hands. `sync` never raises for bd's refusal.

Executable acceptance: `tests/test_reads.py`, `tests/test_writes.py`, `tests/test_classify.py` over recorded bd 1.3.1 JSON in
`tests/fixtures/`, `tests/test_task_read.py` for the shared semantic contract, and `tests/test_boundary_beads_client.py` (stdlib only, no consumer imported).
