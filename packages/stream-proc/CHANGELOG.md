# stream-proc — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.1.0: new  ⇒  `run(argv, cwd=, env=, on_stdout=, on_stderr=, timeout=, idle=, stop=, grace=, prove=, drain=) -> Result(returncode, signal, timed_out, pid, pgid, start, secs, survivors)`, `stop_tree(p, grace=, prove=) -> tuple[int, ...]`, `alive(pid, start=None)`, `proc_start(pid)`, `TermHold`, `popen_held`
