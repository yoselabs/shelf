# any-proc — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.3.0: + `any_proc.cpus` (`available_cpus(cgroup_dir=None) -> int`, `host_cpus()`, `cgroup_quota()`, `Cpus(host, quota).available`); nothing else changed
- 0.2.0: `Health("starting")` terminal, `sup.terminal == "starting"`  ⇒  `State.starting`; `start()` returns it, `supervise()` neither kills nor respawns it
- 0.4.0: depends on `stream-proc>=0.10.0,<1`; `user_task_count()` on macOS counts the user's processes from the libproc table, not from `ps -U uid -o pid=` text; same result, no spawn
- 0.5.0: + `any_proc.testing` (`start_child(argv, **popen_kwargs) -> Child`, `kill_group(child, *, grace=10.0)`, `Child`); nothing else changed
