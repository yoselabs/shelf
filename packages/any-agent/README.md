# any-agent

**Stop writing a new supervisor for every agent CLI.** `claude -p`, `codex exec --json` and `opencode run` are long-running,
tool-using processes: each prints its own stream, retries a limit in its own way and ends in its own words. A **harness** is the
one class that knows a CLI: it builds the launch, parses each output line **once** into typed events and evidence, finds the
transcript and probes the login. `run` supervises any harness the same way, and `classify` turns what the vendor said into one
reason. A sibling of [anyllm](../anyllm/README.md), not a merge: anyllm is an async one-shot `complete()`; a harness is a
supervised process.

Stdlib plus [stream-proc](../stream-proc/README.md) (the shelf's one place that signals a process; itself stdlib-only), so a
vendoring consumer copies both. POSIX only. No consumer's names (lanes, routers, state, holds) appear here: those are injected.

```python
from any_agent import ClaudeHarness, LaunchInputs, RunHooks, classify, run

h = ClaudeHarness()
spec = h.launch_spec(LaunchInputs(exe="claude", cwd=".", model="m", effort="high", prompt="brief", env=env,
                                  session=uuid, system="rules", settings=guard_json, write=False))
out = run(h, spec, timeout=3600, hooks=RunHooks(ref=save_ref, beat=stamp_lease), policy=secret_path_of, gone=lane_marked_out)

s = out.summary                                   # text, rc, res (ref, tokens, turns, acct...), vendor, stderr, work
why = classify(s.rc, s.vendor, s.stderr, out.timed_out, s.work, {"watchdog": out.watch.why and "hung"})
```

## Rules

- **One Harness protocol.** Everything about one CLI lives in its module (`claude.py`, `codex.py`, `opencode.py`): argv, env, event
  parser, usage arithmetic, transcript, login probe, its own regex tables and its measured `limits`. `parse_line` is called once
  per line; the live sink, the turn rules and the classifier all read the same `HarnessEvent` records (`any_agent.events`).
- **Claude's launch rules are in one place.** `claude.launch_argv` never passes `--bare` (it skips OAuth and the keychain, so a
  subscription run would need an API key) and raises `ValueError` if it would. `LaunchInputs.auth` picks exactly one of two modes:
  `subscription` (default; `claude.launch_env` drops `ANTHROPIC_API_KEY` so the run stays on the login) or `api_key` (the key must be in
  the environment, else `ValueError`). `ClaudeHarness.launch_spec` applies both.
- **`run` supervises, the caller injects.** What it needs from the caller comes as callables, never as imports: `live` (a
  `LiveSink`: `started/feed/poll/end`), `gone() -> str | None` (the lane was marked out: stop and say why), `policy(event) -> str | None`
  (a command names a secret path: stop before it uses what it read), `net_up() -> bool` (one probe once the worker has waited
  for the network past 15 s), `log` (a `LogWatcher` over the CLI's own log: opencode retries a limit forever without exiting), and
  `RunHooks` (`started`, `ref`, `beat`, `idle_s`, `unattended`, `stops`).
- **What stops a worker.** The deadline (`timeout`), `Watchdog` (no first line within `first_event_s`; silence past `silence_s`;
  both on a clock that skips a sleeping laptop), `Turn` (a final message then `grace_s` of quiet = `answer`; the model owed a
  response and nothing printed for 900 s = `stall`), the lane check, the log watcher, the network. The whole process tree is
  stopped (SIGTERM, grace, SIGKILL); each stop is a `StopReport` in `hooks.stops`. A caller that dies takes its worker along
  (`unattended`).
- **One ladder.** `classify(rc, vendor_err, stderr, timed_out, work_seen, structured) -> Outcome(reason, detail, source) | None`.
  First match wins: our own facts (secret, watchdog, timeout), a 4xx status we measured, the vendor's words (credit, limit, login,
  bad request, network), then the exit code. The model's answer is never an argument, so a worker that says "rate limit" cannot
  take its lane out. The generic words live in `classify.py`; each harness module owns the patterns only its CLI speaks and the
  ladder merges them. A `None` result means the run is done.
- **Limits are the harness's.** `harness.limits` holds the measured first-event, silence and grace seconds; the caller overrides
  with `run(limits=Limits(...))` and `RunHooks(idle_s=)`.
- **Sandboxed opencode.** `OpenCodeHarness(profile, root, sandbox=Sandbox(readable=..., scratch=..., runners=...))` writes a
  `sandbox-exec` shell (macOS) and a permission table; the caller names what it adds.
- **Beside the harnesses.** `reset_parse` reads a limit message into a reset time (`parse_reset`, `limit_until`);
  `drops.looks_dropped` says a stream broke; `CodexOverlay` is a generated Codex home with an auth symlink.

## What it is not

A router, a lane or lease table, a health or hold record, a cockpit, a publisher or a settler: those stay with the app, which
turns a `classify` reason into effects. It does not install or log in to a CLI, and no part of it calls a model by itself.
