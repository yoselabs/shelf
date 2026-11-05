# any-mailbox

**A one-slot mailbox in a file.** One process posts a message, another takes it once. Bytes in, bytes out: the caller
owns the codec and any identity check. Requires `atomic-io` and `process-lock`.

```python
from pathlib import Path
from any_mailbox import Mailbox

box = Mailbox(Path("run/request.json"))               # lock defaults to run/request.json.lock

box.post(lambda waiting: merge(waiting, new))          # waiting is None when empty; returns True
box.post(lambda waiting: None)                         # None: refuse, leave it as it was; returns False
box.peek()                                             # bytes | None, no lock, never a torn read
box.take()                                             # bytes | None, removed: each message once
```

## Rules

- `post(update)` calls `update(waiting)` under the lock and writes the result atomically, so a post made while a
  `take` runs is never lost and a message is never taken twice. An exception from `update` writes nothing.
- `take()` reads and unlinks under the same lock.
- `peek()` takes no lock; writes are atomic, so it sees a whole message or none.
- The lock is a `process-lock` (the kernel drops it with its process), `timeout=30` seconds by default;
  past it `process_lock.LockHeldError` is raised. Not for level-triggered state: that is a file, not a mailbox.
