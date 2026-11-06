# any-agent — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.1.0: new. `Harness` protocol (`kind`, `limits`, `evidence`, `launch_spec(LaunchInputs) -> LaunchSpec`, `parse_line(line) -> list[HarnessEvent]`, `parse_log_line`, `echoes_input`, `summary(rc, out, err, stop, timed_out) -> Summary`, `vendor_error(rc)`, `transcript(ref)`, `login_probe(timeout)`, `cleanup`, `export`, `log_dir`, `secret_event`); `ClaudeHarness`, `CodexHarness`, `OpenCodeHarness(profile, root, sandbox)`
- 0.1.0: `run(harness, spec, timeout, hooks=None, *, live=None, limits=None, gone=None, log=None, policy=None, net_up=None, clock=...) -> RunOutcome`; `RunHooks(started, ref, beat, idle_s, unattended, stops: list[StopReport])`; `LiveSink` protocol (`started`, `feed`, `poll`, `end`), `NullSink`
- 0.1.0: `classify(rc, vendor_err, stderr, timed_out, work_seen, structured) -> Outcome(reason, detail, source) | None`; reasons `secrets rate_limited credit_exhausted hung network timeout logged_out bad_request killed worker_failed vendor_blip`
- 0.1.0: `claude.launch_argv` raises ValueError on `--bare`; `claude.launch_env(env, auth)` with `LaunchInputs.auth` `subscription` (default; drops `ANTHROPIC_API_KEY`) or `api_key` (needs it, else ValueError); both apply inside `ClaudeHarness.launch_spec`
- 0.1.0: `Limits(first_event_s, silence_s, grace_s)` per harness (`harness.limits`), override with `run(limits=)`; `Watchdog`, `Turn(grace_s)`; no limits table
- 0.1.0: layout `any_agent.harnesses.{claude,codex,opencode,opencode_sandbox,codex_overlay}` and `any_agent.vendors.{common,anthropic,openai,xai}` (`Vendor`, `registry()`, `words(names)`); protocol in `any_agent.protocol`; `classify(..., only=())` and `says_login/says_spend(text, only=())` narrow to named vendors; top-level imports unchanged
- 0.1.0: `reset_parse.parse_reset`, `limit_until`; `opencode_sandbox.Sandbox(readable, scratch, runners)` replaces the caller's folders and recipe runners
- 0.1.0: `gone() -> (why, msg) | None` with `why` in `limit credit logged_out`, carried by `Stop.why`; `classify` structured `watchdog` also takes `credit` (-> credit_exhausted) and `logged_out`; `with_network(outcome, net_up)`, `network_stop(evidence)`, `NET_AMBIGUOUS`; a raising `hooks.started` reaps the tree (report in `hooks.stops`) and re-raises
- 0.1.1: `Denied.reason: str = ""` (why a call was refused: the CLI's or the tool's words, or ours; claude/codex/opencode/supervisor fill it); `LaunchInputs.read_roots: tuple[str, ...] = ()` and `opencode_sandbox.permissions(sandbox, write, engine_only=(), read_roots=())`: a write step reads outside cwd only in the listed roots, a read-only step ignores them
