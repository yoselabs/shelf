# any-gate

**Stop re-running what already passed.** A green result is remembered under a key of exactly what it ran on, so the same
work is not run twice: by a hook, by an agent's manual run, after an amend or a rebase. The key is built by the caller from
whatever its result depends on (file hashes, tool versions, a resolved dependency set); this package never looks inside it.

```python
from pathlib import Path
from any_gate import Receipts, key

receipts = Receipts(Path(".git/gate-receipts.json"))          # plain JSON, any language can read it
k = key(tests=files_hash, python="3.12.4", resolved=lock_hash)
if not receipts.has("tests", k):
    run_the_tests()                                            # raises on red: nothing is recorded
    receipts.record("tests", k)                                # newest first, 50 kept per name
```

| call | job |
|---|---|
| `key(**parts) -> str` | 32 hex of the canonical hash of the parts; the same parts in any order give the same key; a value JSON cannot say is refused |
| `Receipts(path, keep=50)` | the ledger file; `has(name, key)`, `record(name, key)` |

A failure is never recorded. A missing or damaged file remembers nothing and is repaired by the next `record`. Two writers at once
may lose one record (the file is replaced whole, atomically): the cost is one rerun, never a false pass.
