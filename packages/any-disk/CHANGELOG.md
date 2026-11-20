# any-disk — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.1.0: new. `verdict(free_gb, wait, stop) -> "room"|"wait"|"stop"`; `space_verdict(path, *, wait_below_gb, stop_below_gb, disk_usage) -> Verdict`; `await_space(path, *, wait_below_gb, stop_below_gb, poll=300.0, on_wait=None, sleep, disk_usage) -> bool`; `await_space_async(...)` same with awaitable `sleep`; levels in GiB; `stop_below_gb > wait_below_gb` ⇒ ValueError
