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

## The command

```bash
python tools/affected.py --plan | python -m any_gate test --receipts .git/gate-receipts.json -- -p no:cov
```

The plan is `path<TAB>key` per suite on stdin (empty key: never skipped). A suite whose key has a receipt is skipped; the rest run in
stages under a lease (`--slots`, default 1, so gates started at once queue and say who holds the slot), and are recorded when the run is green.
Exit 0: green or nothing to run; 1: a test failed or a stage hit a limit; 2: usage. Arguments after `--` go to every pytest stage. A stage
selects its lane through a pytest plugin (`any_gate.lanes_plugin`), not `-m`, so the repo's own `-m` default stays in force; the plugin
needs `any-gate[pytest]` in the environment of the tests.

### Changed files for per-file linters

```bash
python -m any_gate changed --config pyproject.toml --config ruff.toml 'packages/*.py' 'tests/*.py' | xargs -0 ruff check
```

Prints, NUL-separated, the files that differ from the upstream merge-base (committed, staged, unstaged, untracked and not ignored; a deleted
file never counts) and match a glob. Everything matching is printed instead on `--scope all`, when a `--config` file changed, or with no base
(not a repo, no upstream): run too much rather than too little. `--not GLOB` drops a match. `any_gate.changed.select(...)` is the same in Python.

### The gate's tree record

```bash
python -m any_gate start                                              # first step of the gate: note the working tree
python -m any_gate passed --gate check                                # last step: record it, if no file changed during the run
python -m any_gate pre-push --gate check -- uv run just check         # the hook: skip the gate on a tree that passed it
```

The tree is what `git add -A` would commit; the key adds the upstream merge-base. `pre-push` skips only when the tree is clean, HEAD is what
is pushed (`PRE_COMMIT_TO_REF`) and the key is recorded; anything else runs the command in place of the process. The record is a receipt named
`gate-<gate>` in the same file, so every worktree of a checkout shares it. `GateState(repo, receipts)` is the same in Python.

A failure is never recorded. A missing or damaged file remembers nothing and is repaired by the next `record`. Two writers at once
may lose one record (the file is replaced whole, atomically): the cost is one rerun, never a false pass.
