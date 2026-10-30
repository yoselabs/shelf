# stream-proc — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.1.0: new  ⇒  `run(argv, cwd=, env=, on_stdout=, on_stderr=, timeout=, idle=, stop=, grace=, prove=, drain=) -> Result(returncode, signal, timed_out, pid, pgid, start, secs, survivors)`, `stop_tree(p, grace=, prove=) -> tuple[int, ...]`, `alive(pid, start=None)`, `proc_start(pid)`, `TermHold`, `popen_held`
- 0.2.0: additive, no breaking change  ⇒  `group_alive(pgid) -> bool` (`killpg(pgid, 0)`; PermissionError ⇒ True; pgid <= 1 ⇒ False), `table() -> dict[int, Proc]`, `descendants(root, rows=None)`, `Proc(pid, ppid, pgid, sid, start, state, cpu_s=0.0, cmd="")` (two new defaulted fields); macOS path via libproc/ctypes (`stream_proc.procmac`, selector `stream_proc.proctable`): real start token `<sec>.<usec>` for `alive`/`proc_start`, descendant sweep in `stop_tree`  ⇐  v0.1.0 had no start token and no sweep on macOS; Linux behaviour unchanged
- 0.2.1: fix, no contract change  ⇒  `run` closes the child's stdout/stderr/stdin pipes on every exit path (normal, wall, idle, stop, exception) and ends its reader threads first (they poll the pipe, so a grandchild holding it open no longer pins them); no ResourceWarning for unclosed pipes under `-X dev`  ⇐  v0.2.0 left the two pipe objects to the garbage collector
- 0.2.2: fix, no contract change  ⇒  `TermHold`/`popen_held` hold SIGINT as well as SIGTERM, so a Ctrl-C between the fork and the caller's `try` reaches `stop_tree` (KeyboardInterrupt after the child is known) instead of orphaning its tree; a signal held during a spawn that raises is replayed, not dropped; `TermHold.held` is the list of held signal numbers, `TermHold.old` a dict signum → handler  ⇐  v0.2.1 held SIGTERM only and dropped a held signal on a failed spawn
