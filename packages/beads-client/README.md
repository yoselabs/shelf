# beads-client

A lean, typed, fail-loud client over the `bd` (beads) CLI. Stdlib only; imports no host. Named for the tool it wraps, not
`any-beads`: it wraps exactly one tool.

```python
from beads_client import Bd, BdError, NewBead

bd = Bd("worker-1", cwd="/path/to/repo")
bd.check_version()                       # BdError("version") outside the tested bd range
bead_id = bd.create(NewBead("Fix it", description="...", labels=("shelf",)))
if bd.claim(bead_id):                    # False: someone else holds it
    bd.heartbeat(bead_id)                # refresh the lease
    try:
        bd.update(bead_id, notes="halfway", if_assignee="worker-1", if_status="in_progress")
    except BdError as e:
        if e.kind == "precondition":     # bd exit 13: the fence was stale, nothing written
            ...
    bd.close(bead_id, "done", if_assignee="worker-1")
```

## Verbs

`show`, `comments`, `find`, `ready`, `create`, `create_with_sections`, `update` (with `if_assignee`/`if_status` fences),
`claim`, `unclaim`, `reclaim`, `heartbeat`, `close`, `comment`, `add_label`, `remove_label`, `add_dep`, `remove_dep`, `provenance`, `sync`, `version`,
`check_version`, `at(cwd)`.

## Fails loud

| situation | result |
|---|---|
| `bd` not installed / no answer in time | `BdError` kind `missing_binary` / `timeout` |
| nonzero exit | `BdError` classified by bd's words: `not_found`, `not_claimable`, `precondition`, `lint`, `other` |
| exit 13, or "assignee/status mismatch" | `precondition`: a stale `--if-assignee`/`--if-status`; nothing was written |
| non-JSON, wrong-shaped or id-less reply | `malformed` (a read never turns into "no such bead") |
| `show` with complete issue-absence diagnostics | `None` (the only absence) |
| empty/multiple/mismatched `show` rows; malformed consumed text/dependencies | `BdError("malformed")` |
| backend/table failures or mixed failure diagnostics | `BdError("other")`; never absent |
| `claim`/`unclaim` refused by the holder | `False`; any other failure raises |
| `sync` rejected by the remote under exit 0 (bd 1.3.1) | `SyncResult.code == 1` |
| Dolt lock contention | retried with backoff (`lock_retries`); matched on the lock strings compiled into bd 1.3.1 (`classify.LOCKED`), not yet seen from a live contention |

`close(..., if_assignee=)` and `add_label(..., if_assignee=)` are not atomic: bd has no fence on those verbs, so a same-value `update` fences first and the second call follows it.

Tested against bd 1.3.1 (`TESTED_FROM`..`TESTED_BELOW`); recorded replies live in `tests/fixtures/`. Marks that a driver keeps
on top of bd (task-loop's `held_*`, slot policy, filler wording) are not here.


## Single-task read seam

`TaskReadClient` exposes only `show(task_id, /) -> Bead | None`. `Bd` satisfies it
structurally; its existing constructor and `show(bead=...)` keyword remain unchanged.
The positional protocol does not require mutation, listing or a second task model.

For consumer tests, use `beads_client.testing.FakeTaskReadClient` directly:

```python
from beads_client import BdError, Bead
from beads_client.testing import FakeTaskReadClient

reader = FakeTaskReadClient(
    (Bead("demo-1", title="One", description="Raw requirements"),),
    faults={"demo-unavailable": BdError("timeout", "tracker did not answer")},
)
record = reader.show("demo-1")
assert reader.show("demo-missing") is None
```

Each fake instance represents its own configured backlog. Faults are persistent and
take precedence over seeded records. `task_read_contract(make)` is a plain shared
contract function; owning tests run it against both the semantic fake and real `Bd`
with controlled transport. `Script` remains solely a transport fixture for library tests.

The ready set has the same seam: `ReadyReadClient` exposes `ready(label="", /) -> list[Bead]`, and
`FakeTaskReadClient(records, ready=("demo-1",), ready_fault=None)` seeds which records are ready, in order (it never
computes readiness); `ready_read_contract(make)` checks fake and `Bd` alike.
