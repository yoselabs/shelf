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
- 0.1.2: `classify` structured also takes `setup_failed` (-> setup), `crashed` (-> crash), `signal` (-> killed), `free_model_gone` (-> rate_limited), each with the caller's words as the detail and source `ours`; `CALLER_FACTS`
- 0.1.3: opencode `launch_spec` raises ValueError on `sealed` (no pure-completion guarantee); `LaunchInputs.sealed: bool = False` ⇒ a pure completion; claude: `-p --output-format json --safe-mode --setting-sources "" --tools "" --strict-mcp-config --disable-slash-commands --no-session-persistence --max-turns 1 --system-prompt S [--model M]` (S replaces the default prompt, empty too), codex: `exec --sandbox read-only --skip-git-repo-check --ignore-user-config --ignore-rules --ephemeral [--model M] --json -o F -`; both run in an empty temp cwd that `harness.cleanup()` removes (caller must call it); `claude.sealed_argv`, `any_agent.sealed.SealedDir`; unsealed launches unchanged
- 0.1.4: `launch_env(subscription)` also drops `CLAUDE_CODE_SIMPLE` (what `--bare` sets) and raises ValueError naming `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_USE_BEDROCK`, `CLAUDE_CODE_USE_VERTEX` or `CLAUDE_CODE_USE_FOUNDRY` when set to anything but ""/0/false; `api_key` keeps the env as given; `LANE_ENV`

- 0.2.0: `Worker(pid, pgid, start)` -> `Worker(pid, pgid, start, boot)` with required start; `RunHooks.started` after target launch -> once before target exec; requires `stream-proc>=0.5.0`

- 0.3.0: `decode_answer(text, decode) -> Answer[T]` (`DecodedAnswer(value) | MissingAnswer() | InvalidAnswer(kind, reason)`); strict complete JSON, ValueError-only schema rejection; `testing.FakeRun(outcome, refs=())` consumes one existing four-positional-argument run call, preserving registration/ref/raw outcome facts

- 0.4.0: `LaunchInputs.cli` removed; `CodexHarness.launch_spec` builds fresh/resume argv from model/effort/sandbox/access/isolation; empty optional choices/schema/output omitted, empty nonsealed exe/cwd/explicit resume refused; old arbitrary fresh argv and nonsealed skip-Git extraction removed; sealed completion unchanged

- 0.5.0: no API change; requires `stream-proc>=0.6.0` (adds `run_registered`), released from the same commit so a consumer pins both at one tag

- 0.5.1: no API change; requires `stream-proc>=0.7.0` (line buffer bounded by default via `max_line`), released from the same commit so a consumer pins both at one tag

- 0.6.0: new `any_agent.activity`: `Activity(kind command|tool|message|error|waiting, state running|finished, at, text, id, name, waited_ms, duration_ms, exit_code)`, `Timeline().add(event, now) -> list[Activity]` (folds `HarnessEvent`s and the caller's wall-clock time; a command or tool is a `running` then a `finished` record of one `id`), `encode(a) -> str` / `decode(line) -> Activity | None` (one JSON line); no change to the harnesses or the events

- 0.6.1: `Timeline(scope="")` prefixes every id (a resumed run restarts the vendor's ids); `decode` refuses a non-finite or overflowing `at`, reads `w`/`d` as whole counts clamped to 0..10**12, caps `id` and `name` at 200 characters (`encode` too)

- 0.7.0: `Activity.kind` and `KINDS` gain `think` (`ev.Think` with non-blank text -> one finished record, text capped at 2000); a blank `Think` yields none

- 0.8.0: new `any_agent.access`: `ClaudeAccess(permission_mode: ClaudePermissionMode = auto, settings: str = "")`, `CodexAccess(sandbox: CodexSandbox = workspace-write, approval: CodexApproval | None, network: bool | None, writable_roots: tuple[str, ...])` (closed enums, validated in `__post_init__`), `AccessPolicy`; `LaunchInputs.access_policy: AccessPolicy | None = None`; claude takes `--permission-mode` and `--settings` from it, codex `-s`/`sandbox_mode` plus `approval_policy`, `sandbox_workspace_write.network_access|writable_roots` (`-c`), a policy of another harness raises ValueError; None = unchanged launches (claude `auto` and `LaunchInputs.settings`; codex `LaunchInputs.sandbox` and `access`); opencode unchanged (access = its `Sandbox`)

- 0.9.0: `CodexAccess` adds `exclude_slash_tmp`, `exclude_tmpdir`, `tool_output_token_limit`, `ignore_user_config`, `ignore_rules`, `shell_env: tuple[tuple[str, str], ...]` (`-c shell_environment_policy.set.K="V"`) and `flags()` (exec-only options), `config()` now includes them, `sandbox_argv(exe, command) -> list[str]` (`codex sandbox -c sandbox_mode=... <config> -- command`: the host's enforcement probe); the temp-folder exclusions need workspace-write; token limit > 0
- 0.9.1: codex `agent_message` -> `Msg(final=False)` (exec --json has no phase; only `turn.completed` starts the answer grace, so a commentary message no longer ends the turn after `ANSWER_GRACE_S`)
- 0.10.0: `RunHooks.before_stop: Callable[[str], None] | None` (called with the reason just before each tree stop; a raise is ignored); `StopReport.reason` (`timeout` `secret` `answer` `stall`-as-`hung:<kind>` `limit` `credit` `logged_out` `network` `caller`), `StopReport.term_delivered`, `StopReport.kill_delivered` (a signal call reached something); requires `stream-proc>=0.8.0`
