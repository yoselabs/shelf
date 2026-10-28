# stream-proc — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.1.0: new  ⇒  `run(argv, cwd=, env=, on_stdout=, on_stderr=, timeout=, idle=, stop=, grace=, prove=, drain=) -> Result(returncode, signal, timed_out, pid, pgid, start, secs, survivors)`, `stop_tree(p, grace=, prove=) -> tuple[int, ...]`, `alive(pid, start=None)`, `proc_start(pid)`, `TermHold`, `popen_held`
- 0.2.0: additive, no breaking change  ⇒  `group_alive(pgid) -> bool` (`killpg(pgid, 0)`; PermissionError ⇒ True; pgid <= 1 ⇒ False), `table() -> dict[int, Proc]`, `descendants(root, rows=None)`, `Proc(pid, ppid, pgid, sid, start, state, cpu_s=0.0, cmd="")` (two new defaulted fields); macOS path via libproc/ctypes (`stream_proc.procmac`, selector `stream_proc.proctable`): real start token `<sec>.<usec>` for `alive`/`proc_start`, descendant sweep in `stop_tree`  ⇐  v0.1.0 had no start token and no sweep on macOS; Linux behaviour unchanged
