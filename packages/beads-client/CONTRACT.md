# beads-client

Status: **candidate**. Shape: flexible. Protection is not yet earned by a live consumer.

`Bd(actor, cwd, exe, timeout, run, lock_retries)` runs `bd --actor <actor> <args> --json` through one injectable runner.
Every failure is a `BdError(kind, text, missing_sections)`; kinds: `not_found`, `not_claimable`, `precondition`, `lint`,
`malformed`, `missing_binary`, `timeout`, `version`, `other`. Reads return frozen `Bead`/`Comment`/`Dep` records and treat a
malformed reply as a fault, never as absence. `update(..., if_assignee=, if_status=)` passes bd's fences; exit 13 is
`precondition`. `claim` and `unclaim` answer whether the bead changed hands. `sync` never raises for bd's refusal.

Executable acceptance: `tests/test_reads.py`, `tests/test_writes.py`, `tests/test_classify.py` over recorded bd 1.3.1 JSON in
`tests/fixtures/`, and `tests/test_boundary_beads_client.py` (stdlib only, no consumer imported).
