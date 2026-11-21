# child-env

**Stop copying the env scrub.** The environment a child agent process should get: the caller's own, minus what an
agent session exports and minus credential-looking variables. POSIX only, stdlib only.

```python
from child_env import scrub

env = scrub(os.environ)                          # new dict; the input is never touched
env = scrub(env, keep=["CLAUDE_CONFIG_DIR"])     # rescue a name from the defaults
env = scrub(env, drop=["TASK_LOOP_*", "GIT_DIR"])  # remove the caller's own names
env["DELEGATE_DEPTH"] = "1"                      # add your own after scrubbing
subprocess.Popen(argv, env=env)
```

- `without_venv(env)` (alone, or first: `scrub(without_venv(env))`) also strips an active Python virtualenv, see below.
- `keep` / `drop` entries are exact names, or a prefix when they end with `*`.
- Precedence: `drop` beats everything; `keep` beats the defaults; anything else not matched by a default stays
  (`PATH`, `HOME`, `LANG`, `XDG_*`, `GIT_*`, `TERM`, ...).
- Pure: `scrub` reads no global state; the edge passes `os.environ` in.
- The defaults are exported as tuples: `APP_PREFIXES`, `APP_NAMES`, `CREDENTIAL_PREFIXES`, `CREDENTIAL_NAMES`,
  `CREDENTIAL_MARKERS`.

## Find the program, build the env (allowlist form)

```python
from child_env import NotFound, build_env, find

env = build_env(os.environ, allow=["GIT_*", "OPENAI_API_KEY"], extra={"DELEGATE_DEPTH": "1"})
exe = find("claude", env, extra_dirs=[Path.home() / ".claude" / "local"])   # Exe(path, how="path" | "extra_dir")
subprocess.run([str(exe.path), "--version"], env=env)                       # find raises NotFound, never returns "claude"
```

- `build_env`: only `DEFAULT_INHERIT` (`PATH`, `HOME`, `USER`, `LANG`, `LC_*`, `TERM`, `TMPDIR`, `TZ`, `XDG_*`, ...)
  and `allow` names pass; the secret rules of `scrub` still drop a name under an allowed prefix, only an exact `allow`
  name rescues one. `extra` is set last.
- `find`: searches `env["PATH"]` then `extra_dirs`; `NotFound.searched` lists every folder tried. Never reads
  `os.environ`. `tests/test_arch_exe_env.py` bans `shutil.which` and `env=os.environ` outside this package.

## What is removed by default

Agent-session variables (a standalone `claude` or `codex` started with them misbehaves):

| Rule | Why |
|---|---|
| prefix `CLAUDE_` (`CLAUDE_CODE_*`, `CLAUDE_PID`, `CLAUDE_PLUGIN_*`, `CLAUDE_AGENT_SDK_*`, `CLAUDE_CONFIG_DIR`) | the launcher's session, plugin and config identity |
| prefix `ANTHROPIC_` | `ANTHROPIC_BASE_URL` and friends make a keychain login look expired; also carries `ANTHROPIC_API_KEY` |
| prefix `DELEGATE_`, `CODEX_COMPANION` | the delegate and Codex-companion plumbing of the parent |
| prefix `MCP_`, `OTEL_` | MCP and telemetry settings of the parent session |
| `CLAUDECODE` | says "nested session" |
| `AI_AGENT`, `API_TIMEOUT_MS`, `BAGGAGE`, `DISABLE_MICROCOMPACT`, `DISABLE_AUTOUPDATER` | other things the Claude app exports |
| `USE_LOCAL_OAUTH`, `USE_STAGING_OAUTH` | switch the login server |

Credentials (a worker should not inherit the launcher's secrets), matched case-insensitively:

| Rule | Why |
|---|---|
| name contains `TOKEN`, `SECRET`, `PASSW` (PASSWORD, PASSWD, PGPASSWORD), `CREDENTIAL` | bearer tokens, client secrets, passwords, credential files/blobs |
| name contains `API_KEY` / `APIKEY`, `ACCESS_KEY` / `ACCESSKEY`, `PRIVATE_KEY` / `PRIVATEKEY` | API keys, cloud access keys, SSH/TLS private key material |
| prefix `AWS_` | the whole AWS credential and profile chain (`AWS_PROFILE` selects credentials) |
| prefix `GH_`, `GITHUB_` | `GH_TOKEN`, `GITHUB_TOKEN`, and the GitHub CLI/Actions context |
| `SSH_AUTH_SOCK` | the ssh agent signs as the user |

Known false positives: anything with the marker words in a harmless name (`TOKENIZERS_PARALLELISM`, a `GITHUB_*`
feature flag). Rescue them with `keep`.

## Virtualenv strip (opt-in)

A child that inherits our `VIRTUAL_ENV` runs in our venv (the task-loop leak of 2026-10-30). Off by default;
`without_venv(env)` (or `scrub(without_venv(env))` for both) removes `VENV_NAMES` (`VIRTUAL_ENV`, `VIRTUAL_ENV_PROMPT`,
`PYTHONHOME`, `__PYVENV_LAUNCHER__`, `PYTHONEXECUTABLE`) and, when `VIRTUAL_ENV` is set, the exact entry
`$VIRTUAL_ENV/bin` from `PATH` (other entries and their order stay; with no `VIRTUAL_ENV`, `PATH` is untouched).
Applied first, it wins over `keep`, and still cleans `PATH` when `drop` names `VIRTUAL_ENV`. `PYTHONPATH`, `UV_*` and
the rest are not touched. There is no allowlist mode.

## Provenance: two copies, one union

Promoted from `iorlas-task-loop` (`skills/task-loop/core/procs.py` `child_env`) and `iorlas-delegate`
(`skills/delegate/onboard.py` `APP_ENV_RE`/`app_free_env` and `route.py` `CREDENTIAL_RE`/`child_env`). The default
is the union of what both remove; both stay on a pure superset of what they accepted, with these differences:

| | task-loop | delegate | child-env default |
|---|---|---|---|
| `CLAUDE_*` | only `CLAUDE_CODE_`, `CLAUDE_PID`, `CLAUDE_AGENT_SDK`, `CLAUDE_PLUGIN`; so `CLAUDE_CONFIG_DIR` survives | all `CLAUDE_*` | all `CLAUDE_*` (use `keep=["CLAUDE_CONFIG_DIR"]` for task-loop's behaviour) |
| `ANTHROPIC_`, `DELEGATE_`, `CLAUDECODE` | removed | removed | removed |
| `CODEX_COMPANION` | prefix, no underscore | `CODEX_COMPANION_*` | prefix `CODEX_COMPANION` |
| `MCP_`, `OTEL_`, `AI_AGENT`, `BAGGAGE`, OAuth switches, ... | kept | removed | removed |
| credentials (`*TOKEN*`, `AWS_*`, ...) | kept | removed | removed |
| `TASK_LOOP_*` | removed | kept | kept: pass `drop=["TASK_LOOP_*"]` |
| `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE` | removed | kept | kept: pass `drop=` them |
| sets `TASK_LOOP_WORKER=1` / `DELEGATE_DEPTH=1` | yes | `DELEGATE_DEPTH=1` | no: set them on the result |

Notes: delegate matched the app names case-sensitively and anchored (`CLAUDE_\w*`); the union matches by prefix, so
a variable like `CLAUDE_` + anything is covered either way. Credential matching keeps delegate's case-insensitive
rules unchanged.

## Boundary

Imports no consumer app (`a2web`, `a2kay`) - enforced by `tests/test_boundary_child_env.py`.
