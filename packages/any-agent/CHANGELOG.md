# any-agent — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.1.0: new. `Harness` protocol (`kind`, `limits`, `evidence`, `launch_spec(LaunchInputs) -> LaunchSpec`, `parse_line(line) -> list[HarnessEvent]`, `parse_log_line`, `echoes_input`, `summary(rc, out, err, stop, timed_out) -> Summary`, `vendor_error(rc)`, `transcript(ref)`, `login_probe(timeout)`, `cleanup`, `export`, `log_dir`, `secret_event`); `ClaudeHarness`, `CodexHarness`, `OpenCodeHarness(profile, root, sandbox)`
- 0.1.0: `run(harness, spec, timeout, hooks=None, *, live=None, limits=None, gone=None, log=None, policy=None, net_up=None, clock=...) -> RunOutcome`; `RunHooks(started, ref, beat, idle_s, unattended, stops: list[StopReport])`; `LiveSink` protocol (`started`, `feed`, `poll`, `end`), `NullSink`
- 0.1.0: `classify(rc, vendor_err, stderr, timed_out, work_seen, structured) -> Outcome(reason, detail, source) | None`; reasons `secrets rate_limited credit_exhausted hung network timeout logged_out bad_request killed worker_failed vendor_blip`
- 0.1.0: `claude.launch_argv` raises ValueError on `--bare`; `claude.launch_env` drops `ANTHROPIC_API_KEY`; both apply inside `ClaudeHarness.launch_spec`
- 0.1.0: `Limits(first_event_s, silence_s, grace_s)` per harness (`harness.limits`), override with `run(limits=)`; `Watchdog`, `Turn(grace_s)`; no limits table
- 0.1.0: `reset_parse.parse_reset`, `limit_until`; `opencode_sandbox.Sandbox(readable, scratch, runners)` replaces the caller's folders and recipe runners
