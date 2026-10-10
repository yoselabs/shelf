# Prior art for `blueprint`: agent-harness + agent-weiss

Sources: `~/Workspaces/agent-harness` (200 commits, 2026-03-22 → 04-19), `~/Workspaces/agent-weiss` (52 commits,
2026-04-19 01:14 → 16:09). Both frozen on 2026-04-19.

## 1. What each built

### agent-harness (CLI `agentic-harness` on PyPI, v0.3.3) — a linter runner
- Shape: Python CLI (`detect / init [--apply] / lint / fix / security-audit / security-audit-history`), ~3.7k LOC.
  `presets/<stack>/` (universal, python, javascript, docker, dokploy), each implementing
  `detect() run_checks() run_fix() run_setup() get_info()`; one check per file with a WHAT/WHY/WITHOUT IT/FIX/REQUIRES
  docstring; `policies/<area>/*.rego` deny-only, each with a `_test.rego` sibling (109 Rego tests, 201 py tests).
- Skill `skills/agent-harness/SKILL.md`: 3 phases Discover → Plan (A→B diff, grouped by file) → Execute
  (`init --apply`, hooks, `make check`, commit, report). Plus guidance docs (python knobs, docker recipes, monorepo traps).
- Three-layer placement rule (CLAUDE.md): "Would any reasonable person agree this is broken?"
  YES → lint (Rego deny, every commit) · debatable → init (Python `SetupIssue`, critical|recommendation, auto-fixable,
  safe blind) · needs intent → skill (agent judgment).

Rego policies (17 files, 44 deny rules):

| id | checks |
|---|---|
| gitignore.secrets | `.env` always; `.venv`/`__pycache__` (py), `node_modules`/`dist` (js) |
| python.ruff | `output-format=concise`; `line-length>=120`; mccabe max-complexity ≤15 (rec 10) |
| python.pytest | addopts `--strict-markers`, `--cov`, `--cov-fail-under` present and ≥30 |
| python.coverage | `report.skip_covered=true`; `run.branch=true` |
| python.test_isolation | pytest-env `env` block present (test DB etc.) |
| javascript.package | `engines`; `"type":"module"`; no `*` versions |
| dockerfile.user / .healthcheck | USER present; HEALTHCHECK present |
| dockerfile.layers / .cache | manifests copied+installed before source; `--mount=type=cache` on dep install |
| dockerfile.secrets / .base_image | no secret-looking ENV/ARG; no alpine with python/node/ruby |
| compose.services | healthcheck; restart policy; no 0.0.0.0 port binding |
| compose.images | no `build:`; mutable tag needs `pull_policy: always`; no implicit latest; own images pinned |
| compose.escaping / .volumes / .configs / .hostname | bare `$`; no bind mounts; no inline `content:`; hostname on dokploy-network |
| dokploy.traefik | `traefik.enable=true`; on `dokploy-network` |

Non-Rego lint checks: ruff check+format, ty, biome, framework type-check (astro check > next lint > tsc), hadolint,
yamllint, conftest JSON parse, file-length (500 .py/.ts, 800 .vue/.astro), tracked-but-gitignored files,
pre-commit hooks *installed* (respects `core.hooksPath`), osv-scanner (deps), gitleaks (tree + `--full-history`).
Init-only checks (`SetupIssue`): pytest `-v`; `--cov-fail-under` 90–95; skip_covered; branch; .gitignore completeness vs
vendored github/gitignore templates (grouped append); CLAUDE.md mentions `make check/lint/fix`, hooks, "never truncate
output" (+ `make test`, `coverage-diff` for py); osv/gitleaks installed.
Skill-only audits: Makefile table (duplicated work, bypassed tools, conflicting fix targets, missing delegation,
pre-commit misalignment, fix-before-lint, stale targets, redundant security tooling); .gitignore stale patterns.

- Verdicts: lint `PASS/FAIL name (ms)`, summary `N passed, M failed (476ms)`; skill report ✅ pass / ⚠️ fixable /
  ❌ blocking, **every check prints a line, passes included**; final report lists Changes / Verification / Skipped
  (with reason) / Manual attention.
- State: `.agent-harness.yml` — `stacks`, `exclude`, per-stack thresholds, `conftest_skip: {file: [policy.id]}`
  (19 skippable ids), `security.ignore: [{id, expires}]` (expired ignores stop applying).
- Templates scaffolded: Makefile (`lint fix test check security-audit bootstrap`; py adds `coverage-diff` via
  diff-cover `--fail-under=95` vs origin/main; `check: lint test coverage-diff security-audit`), pre-commit
  (fix then lint, `always_run`), CLAUDE.md (dev-commands block), GH Actions CI (setup-uv cache, `uv sync --frozen`,
  runs `make` targets), Python Dockerfile, .yamllint.yml.

### agent-weiss (skill-only, "no CLI") — a setup/audit state machine
- Shape: `profiles/<profile>/domains/<domain>/controls/<control>/` with `prescribed.yaml` (id, version, what, why,
  applies_to, install per-OS), `check.sh`, optional `policy.rego`+`policy_test.rego`, `instruct.md` (why + how to fix +
  when to override). `bundle.yaml` single version. Python lib (1.45k LOC): bundle resolver, state, reconcile, hashing,
  schemas, setup/{gap, batch, verbs, cascade, apply, backup, dry_run}, verify/{dispatch, score, report}.
- Controls built (16): universal.docs.{agents-md, claude-md, readme}-present · universal.security.{gitignore-secrets,
  env-files-not-tracked, gitleaks-precommit} · universal.vcs.{gitignore-present, license-present} ·
  python.quality.{ruff-config, ty-config} · python.testing.{pytest-config, coverage-config, test-isolation} ·
  typescript.{project-structure.package-json, quality.biome-config, testing.vitest-config}.
  6 are Rego ports from harness, 7 are `test -f`; zero new rules. Docker deferred.
- `check.sh` contract: one JSON line `{status: pass|fail|setup-unmet, findings_count, summary, install?, details_path?}`,
  exit 0/1/127.
- Scoring: **Setup** (configured?) = 100/0 per control, setup-unmet = 0, override-with-reason = 100; avg per domain,
  avg of domains. **Quality** (passing?) = 100/0, setup-unmet excluded, domain `n/a` if all unmet. Never cached.
  Glyphs ✓ ✗ ⚠(setup-unmet) ⊘(override).
- State `.agent-weiss.yaml`: bundle_version, profiles, overrides {control: {reason}}, `prescribed_files`
  {path: sha256, bundle_path, last_synced}, custom_policies, drift. Classes: prescribed-clean /
  prescribed-locally-modified / custom / override. Reconcile pass detects ghosts, orphans, removed bundle paths.
- Approval UX: numbered proposals batched by domain; verbs `approve all | approve <domain> | 1,3 | skip N: reason |
  explain N | dry-run | cancel`; skipping a dependency prompts about dependents (`depends_on` cascade).
- Safety: never auto-install tools, backup before overwrite, dry-run report file.

## 2. What worked, what was abandoned, why

Worked (evidence: shipped + dogfooded):
- Harness deny-only Rego with WHAT/WHY/FIX and test siblings; messages are fix instructions
  ("missing 'skip_covered' — set to true so agents only see files with gaps").
- Lint/init/skill boundary by "objectively broken vs debatable vs needs intent".
- Applying itself to itself (`chore: apply agent-harness to itself`), real-project trials (aggre, the owner's website).
- Expiring ignore lists; per-file named exceptions instead of blanket disables.

Abandoned / stalled:
- Harness: v0.3.3 on PyPI, then stopped. Its own v1-vision doc diagnoses the tool-wrapper trap (Biome 2.x dropped
  `--check`, wrappers break). Its last 13 commits are weiss spec/plans/roadmap — harness became weiss's planning repo.
- Weiss: spec v1→v3 through three review passes before code; roadmap of 6 plans; 4 plans executed in ~15 h.
  `INSTALL_FILE`/`MERGE_FRAGMENT` still raise `NotImplementedError` ("Plan 3 limitation") — **after 4 plans the skill
  could not write one file**; every proposal is MANUAL_ACTION ("show instruct.md, ask 'done?'").
  `gap.py` proposes every applicable control regardless of check result (check-driven gaps "Plan 4 will tighten").
  HANDOVER.md ends on an unanswered "execute Plan 5 (distribution: Claude marketplace + PyPI + npm) or review?".
- Weiss contract inverted in practice: all 9 existence controls emit `fail` for a missing file; only the Rego runner
  emits `setup-unmet` (conftest absent). So a missing AGENTS.md scores Setup 100 / Quality 0 — opposite of the spec.
  No fixture `pass/`/`fail/` dirs exist despite the spec's testing strategy.
- Spec promised 30–40 controls; 16 built, 0 new.

## 3. Carry into blueprint

Blueprint's planned list: stack, strict linters, layering, BDD, Makefile gate, Docker/CI, beads, openspec, ADRs, shelf
onboarding, agent instructions. Items below are what prior art adds beyond that list.

Checkpoints:
| item | verdict | why |
|---|---|---|
| Agent-readable output: ruff `output-format=concise`, pytest `-v`, coverage `skip_covered`+`branch` | ✅ take | "strict linters" alone never produces these; they cut agent context noise |
| pytest `--strict-markers` + `--cov-fail-under` (floor, recommended 90–95) | ✅ take | silent zero-test runs; coverage gate must exist |
| mccabe/complexity cap | ✅ take | cheap, deterministic, curbs sprawling functions |
| Test isolation (pytest-env / test env vars, no prod DB) | ✅ take | real agent failure mode, not on blueprint's list |
| `.env` gitignored + no tracked-but-ignored files + gitleaks pre-commit + osv-scanner | ✅ take | security is absent from blueprint's list entirely |
| Ignore lists carry an `expires` date | ✅ take | matches shelf's "resolutions expire" doctrine |
| Pre-commit hooks *installed* (not just configured), fix-before-lint order | ✅ take | config-present ≠ gate active |
| `make bootstrap` (fresh clone → green) | ✅ take | an agent in a new worktree needs one command |
| `coverage-diff` (diff-cover vs main) inside `make check` | ✅ take | stops new uncovered code without a global-threshold fight |
| CI runs `make` targets, not raw tools; `uv sync --frozen` | ✅ take | one gate definition, local == CI |
| GH Actions pinned SHAs + `permissions:` block (harness TODO, never built) | ✅ take | supply-chain, deterministic to check |
| AGENTS.md *content* audit (names the gate, fix cmd, hooks, never-truncate-output) | ✅ take | existence check is worthless; content check is the value |
| Makefile audit table (bypassed tools, duplicated work, missing delegation) | ✅ take | exactly the drift found in real repos |
| Dockerfile: USER, HEALTHCHECK, deps-before-source, cache mount, no secret ENV/ARG, no alpine+py | ✅ take | "Docker/CI" in blueprint has no rule list; these are proven |
| compose: healthcheck, restart, 127.0.0.1 binding, pinned own images | ✅ take | same |
| package.json engines / ESM / no `*` | ✅ take, only if a TS stack is offered | |
| LICENSE present, README present | ❌ leave | existence checks with no agent payoff; noise in the score |
| dokploy/traefik, compose volumes/inline configs/hostname | ❌ leave | deployment-platform rules, not agent-readiness |
| 500-line file cap | ❌ leave | harness TODO admits "no data"; shelf constitution: structure controls size, not caps |
| yamllint / JSON-parse checks | ❌ leave | marginal; parsers fail loudly anyway |

Formats and mechanics:
| item | verdict | why |
|---|---|---|
| Setup vs Quality split (configured? vs passing?) | ✅ take | empty repo = every Setup checkpoint fails, Quality n/a — exactly blueprint's premise |
| Override with written reason = pass | ✅ take | rewards a decision; mirrors shelf's ADR culture |
| Every checkpoint prints a line, passes included; report has Skipped-with-reason | ✅ take | nothing invisible; makes audits diffable |
| One-JSON-line + exit-code check contract (0 pass / 1 fail / 127 unmet) | ✅ take, with a self-test that enforces it | weiss wrote it and broke it |
| Checkpoint = id + what + why + check + fix (+ when to override) | ✅ take | weiss's `prescribed.yaml`+`instruct.md` split is the good part; fold into one file per checkpoint (constitution: one concept per file) |
| Error message = fix instruction | ✅ take | harness's strongest trait |
| Placement rule: objectively broken → gate; debatable → audit; intent → agent judgment | ✅ take | stops every rule becoming a hard fail |
| Per-checkpoint pass/fail fixture repos run in the repo's own tests | ✅ take | the only way to stop contract drift |
| Rego/conftest as the check engine | ❌ leave | Go binary dep (harness TODO questions it), JSONC breaks it; shelf stack is Python — write checks in Python/pytest. Caller decision if a polyglot policy language is wanted |
| Numbered approval verbs (`approve <domain>`, `skip N: reason`, `explain N`, `dry-run`) | ✅ take as prose convention | cheap, works in chat; ❌ the 1.45k-LOC parser/cascade library behind it |
| sha256 `prescribed_files`, reconcile, ghosts/orphans, backups, bundle_version drift | ❌ leave | only needed if blueprint ships files it must later re-sync; git already gives undo + diff |
| 3 distribution channels / bundle resolver | ❌ leave | shelf already distributes by git tag |
| Scores averaged per domain, numeric 0–100 | ❌ leave | binary 100/0 averaged hides which gate is missing; a pass/fail list per checkpoint is the honest output |

Scripts/templates worth lifting verbatim (then adapt to shelf toolchain: pyrefly not ty, `make check` as the one gate):
- Makefile template incl. `bootstrap` and `coverage-diff` (`agent-harness/src/agent_harness/init/templates.py`).
- GH Actions CI template (`presets/python/templates.py` `CI_WORKFLOW`), Dockerfile template (uv slim, cache mounts).
- docker-guidance.md healthcheck recipes (postgres, redis, mysql, http, distroless), migration-as-one-shot pattern.
- Vendored github/gitignore templates + grouped-append logic (`presets/universal/gitignore_setup.py`).

## 4. Anti-patterns blueprint must avoid
- Plumbing before value: weiss built state/reconcile/hash/verbs/cascade/backup before any control could write a file.
  Blueprint's first deliverable must be one checkpoint that audits AND sets up end to end.
- Spec-and-roadmap-first: 3 spec revisions + 6-plan roadmap, then stall at plan 5. Shelf doctrine already says
  do not build on spec.
- Distribution-first: weiss stalled designing marketplace + PyPI + npm for a skill nobody had run on a real repo.
- Tool-wrapper trap: harness wrapped ruff/biome invocations and broke on CLI changes. Blueprint should check config
  and delegate execution to `make check`, never re-implement runners.
- One topic in three surfaces (Rego lint + Python init + skill prose) with no single truth per rule.
- Contract without enforcement: weiss's exit-127 contract violated by 9/16 controls, unnoticed, no fixtures.
- Existence checks padding the count (README/LICENSE/AGENTS.md-present) — inflate scores, prove nothing.
- Scope creep into deployment platform (Dokploy) inside an agent-readiness tool.
- Two repos for one idea, planning living in the predecessor repo; rename-driven restarts (ai_harness → agent-harness
  → agent-weiss) instead of evolving one artifact.
- Unchallenged numbers baked into rules (500 lines, line-length 120) — harness TODO flags them as "no data".
