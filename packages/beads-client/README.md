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
`claim`, `unclaim`, `reclaim`, `heartbeat`, `close`, `comment`, `add_label`, `remove_label`, `provenance`, `sync`, `version`,
`check_version`, `at(cwd)`.

## Fails loud

| situation | result |
|---|---|
| `bd` not installed / no answer in time | `BdError` kind `missing_binary` / `timeout` |
| nonzero exit | `BdError` classified by bd's words: `not_found`, `not_claimable`, `precondition`, `lint`, `other` |
| exit 13, or "assignee/status mismatch" | `precondition`: a stale `--if-assignee`/`--if-status`; nothing was written |
| non-JSON, wrong-shaped or id-less reply | `malformed` (a read never turns into "no such bead") |
| `show` of an unknown bead | `None` (the only absence) |
| `claim`/`unclaim` refused by the holder | `False`; any other failure raises |
| `sync` rejected by the remote under exit 0 (bd 1.3.1) | `SyncResult.code == 1` |
| Dolt lock contention | retried with backoff (`lock_retries`); words are unconfirmed, see `classify.LOCKED` |

Tested against bd 1.3.1 (`TESTED_FROM`..`TESTED_BELOW`); recorded replies live in `tests/fixtures/`. Marks that a driver keeps
on top of bd (task-loop's `held_*`, slot policy, filler wording) are not here.
