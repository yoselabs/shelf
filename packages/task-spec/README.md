# task-spec

**A task is a specification.** The model and the ports every task tool shares; stdlib only, no tracker named.

```python
from task_spec import Task, Trust, Finding, Remedy, TaskStore, AttentionStore

task = Task(id="t-1", title="Add X", why="...", touches=("pkg/x.py",), acceptance=("pytest -> exit 0",), trust=Trust.OWNED)
Finding(task="t-1", repo="shelf", rule="acceptance-checkable", remedy=Remedy.MECHANICAL, why="no command")
```

## Rules

- `Trust` is `proposed` (an agent filed it) or `owned` (the owner wrote or raised it); an engine runs only `owned`.
- A `Finding` carries who can fix it: `owner`, `mechanical` or `agent`.
- `TaskStore` (get, all, save) and `AttentionStore` (ask, pending, resolve) are protocols; a tracker adapter implements them.
  A task ask is an `AskKind` and ends in one typed edit of the task.
- `task_spec.testing` holds in-memory stores and `task_store_contract` / `attention_store_contract`, plain functions that
  raise AssertionError: run them against any adapter.
