# Changelog

## 0.3.0

- breaking: `scrub(..., strip_venv=)` and `scrub_current(strip_venv=)` removed; strip the venv with `scrub(without_venv(env), ...)` (same result for every keep/drop). `without_venv` unchanged.

## 0.2.0

- `find(name, env, extra_dirs=())` returns an `Exe(path, how)` or raises `NotFound(name, searched)`: the one binary
  lookup. PATH is the injected `env`'s (never the process's), then `extra_dirs`; a miss never hands back the bare name.
- `build_env(env, *, allow=(), extra=None)` and `DEFAULT_INHERIT`: an allowlist child env; secrets never pass unless
  named exactly.

- `without_venv(env)`, `VENV_NAMES` and `scrub(..., strip_venv=True)` (also `scrub_current`): strip an active Python
  virtualenv (`VIRTUAL_ENV`, `VIRTUAL_ENV_PROMPT`, `PYTHONHOME`, `__PYVENV_LAUNCHER__`, `PYTHONEXECUTABLE`, and the
  venv's `bin` entry in `PATH`). Off by default; promoted from iorlas-task-loop `without_venv`.

## 0.1.0

- `scrub(env, *, keep=(), drop=())` and `scrub_current(...)`: an environment without `CLAUDE_*`, `ANTHROPIC_*`,
  `DELEGATE_*`, `MCP_*`, `OTEL_*`, `CODEX_COMPANION*`, the other Claude-app exports and credential-looking variables.
- Default tuples exported; `keep` and `drop` take exact names or `PREFIX*`.
- Promoted from iorlas-task-loop `child_env` and iorlas-delegate `app_free_env` / `child_env` (union of both).
