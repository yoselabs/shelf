# Shelf machinery blueprint delegates to (one pass, 2026-10-10)

Condensed from an Explore pass over the shelf repo. Paths relative to the shelf root.

## Wiring a consumer
- `make bootstrap` / `make bootstrap-verify` → `.agents/skills/onboard-consumer/scripts/onboard.py --repo .`
  Operations in `tools/onboard/`: guard → resolver-block → beads (requires guard) → linter-preset
  (python+uv only). Each returns `Result(outcome, verified, message)`; exit 0 only if all satisfied.
- `make guard` → `tools/hooks/forbid-local-shelf-source.py --committed` (no `path=` shelf source in HEAD).
- `make preset` → `tools/preset_drift.py --repo .` (ruff select/ignore, pyrefly errors, Make targets
  vs shelf; excused only via `[tool.shelf-preset]`). Exit 2 = cannot verify, never a pass.
- `tools/hooks/install.py` installs `shelf-guard` + `shelf-lint` hook spans, refuses foreign hook
  managers and names where to add instead.
- Resolver block text: `BLOCK_TEXT` in `tools/onboard/resolver_block.py`.

## Lint preset (python-uv)
- ruff py311, line-length 140, curated-broad select (F E W PL* B BLE TRY RSE EM RET SIM C4 C90 PIE
  FURB FLY ANN UP FA TC PYI I TID ICN INP A N SLF S DTZ LOG G T10 T20 ASYNC PTH FBT ISC ERA ARG PERF
  RUF), `D` absent; ignore ANN401 PLR0913 PLR2004 ISC001 TRY003 S603 S607; mccabe 12.
- pyrefly `preset = "strict"` + correctness opt-ins as "error"; tests via sub-config.
- codespell, deptry per package, pytest `--strict-markers`, coverage branch, floor 65 (Makefile).
- Reference doc: `docs/linting.md`.

## Architecture fitness
- `tests/test_boundary.py` (no package imports a consumer), `tests/test_arch_rules.py` via
  `tools/arch_rules.py` (dep upper bound, body duplication, private-name collision; allowlist with
  reasons in `tests/arch_allowlist.toml`), `make advisory` (non-blocking).
- Layer DAG and `dict[str, Any]` ban: not ported (per `docs/linting.md`).

## Testing packages a consumer gets
- `bdd-tags` (pytest11 plugin: `@spec:`/`@bug:` traceability, `@known_bug:<id>` strict xfail, `@pending` skip).
- `mcp-steps` (one MCP session per actor; step `{actor} calls "{tool}" with:` + JSON docstring).
- `json-match` (`dig`, `compare`, `matches`; absent ≠ null).
- `testing` modules: `a2effect.testing` (envelope contract tests, refusal step), `git_porcelain.testing`
  (hermetic git env), `launchd_agent.testing` (fake/refusing launchctl), `anyllm.testing`
  (hermetic LLM env), `anyembed.testing` (`HashEmbedder`).

## Loop and governance
- `docs/agent-loop.md`: SESSION-RESOLVE, SEAM, PROMOTE, RECEIVE, RECONCILE, BENCH, ESCAPE-HATCH,
  EVOLVE-THE-LOOP.
- Skill Kind contract: `openspec/specs/skill-kind/spec.md`, `openspec/specs/shelf-plugin-distribution/spec.md`,
  `tests/test_gate_covers_every_skill.py`, `.claude-plugin/{marketplace,plugin}.json`.
- CI: `.github/workflows/check.yml` runs `uv sync && make check` on push/PR. No Docker anywhere.

## Defects found (filed)
- shelf-4mz linter-preset omits `preset` target, `[tool.pyrefly]`, pytest config.
- shelf-4f2 onboard.py does not check `../shelf` despite its message.
- shelf-zox CI browser lane claimed in comments, absent in `check.yml`.
- shelf-dzl `docs/tracks/` referenced, absent.
- shelf-0h1 AGENTS.md `make check` comment omits guard and preset.
