# any-supervise — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.1.0: new. `load_spec(path) -> Spec` (TOML: `state`, `version_cmd`, `version_cwd`, `[[worker]]` name/command/count=1/cwd="."/log/env/env_pass/stop_timeout_s=30; relative paths against the spec folder; `{index}`/`{count}` in argv; env `ANY_SUPERVISE_INDEX`/`ANY_SUPERVISE_COUNT`); `Host(environ, clock=time.time, sleep=time.sleep)` (workers get `child_env.build_env(environ, allow=env_pass, extra=env + ANY_SUPERVISE_*)`)
- 0.1.0: `status(spec, host) -> tuple[ReplicaStatus]` (`State` = running | stale | dead | missing | orphan; reads only), `up(spec, host) -> tuple[Started]` (idempotent), `roll(spec, host, *, parallel=1, names=(), settle_s=3.0) -> tuple[Rolled]`, `down(spec, name=None) -> tuple[Stopped]`, `logs(spec, name, lines=50) -> tuple[str]`, `current_version(spec, host) -> str`
- 0.1.0: state file `<state>/<replica>.json` = `name, pid, start, argv, version, started_at`; identity = pid alive AND `start` equal (stream-proc token), else never signalled; mutating verbs hold `<state>/.lock` (second one raises `BusyError`)
- 0.1.0: errors share `SuperviseError`: `SpecError`, `StateError`, `VersionProbeError`, `UnknownNameError`, `StopFailedError(replica, survivors)`, `ReplacementDiedError(replica, log)`
- 0.1.0: CLI `any-supervise up|status [--json]|roll [--parallel N] [--settle S] [NAME...]|down [NAME]|logs NAME [-n N] SPEC`; exit 0 ok, 1 status not all running, 2 failure
- 0.1.0: `roll` first starts the dead or missing replicas of every lane it rolls (they come back on the current version), so a lane never drops to zero
