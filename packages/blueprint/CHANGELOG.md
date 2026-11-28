# Changelog

## Unreleased

- **Tool config in `.config/`, caches in `.cache/` (ADR 0035, shelf-mkfd).** New row `layout.root-files-in-config` (waivable, ADR 0018): fails a repo with `.gitleaks.toml`, `.hadolint.yaml`, `.yamlfmt.yaml`, `.dclintrc`, `typos.toml` at the root (the remedy is the `git mv` into `.config/`), or a used ruff or coverage with no cache setting under `.cache/` (the remedy is the exact setting). It lists only what the tool reads elsewhere when told to (measured in the ADR) and what the engine follows: a repo that cannot move a file never fails it. The rendered `images` step passes `hadolint -c`, `yamlfmt -conf` and `dclint -c` when the config is in `.config/` (its inputs list them); the secret scan passes `--config` for `.config/gitleaks.toml` or the root file (also for its temp copy of untracked files, which found no config before); the stack config rows accept the `.config/` names; rendered `arch` passes `lint-imports --cache-dir .cache/import_linter` and `python.just` exports `HYPOTHESIS_STORAGE_DIRECTORY` into `.cache/`. New row `layout.one-config-per-tool` (waivable): one tool (ruff, tsconfig, biome, eslintrc, gitleaks, hadolint, yamlfmt, dclint, typos, prettier) configured in two folders with at least 70% equal settings fails, naming the pair and the tool's extend mechanism or `cannot extend: waive`; a file that extends is a delta. Not yet: the hook config, `mise.toml`, `gate-inputs.toml`, `.blueprint/` and `deploy/` (beads filed). Corpus diff (42 repos): `layout.root-files-in-config` fails 20 (ruff cache 18, coverage 11, `.hadolint.yaml` 7, `.gitleaks.toml` 2, `.yamlfmt.yaml` 2, `.dclintrc` 2, `typos.toml` 2; each has a move or setting it can make), passes 22; `layout.one-config-per-tool` fails 0 (closest pair 62%).

## 0.19.1

- **The Python stack in `backend/` (shelf-meqv, a2kay: 8 rows read the repo root).** The six `framework.mcp.*` rows read `pyproject.toml`, `uv.lock` and `tests/` through the Python folder (`{py}` in `profiles/frameworks/mcp.toml`). `stack.node.spelling` and `stack.compose.spelling` accept the Python folder's `[tool.codespell]` when its `spell-paths` (relative to that folder) reach every file of the stack (`codespell-covers` in the profile); no `spell-paths`, or paths that miss the frontend or the compose file, still fail. `gate.lint-paths-cover-python` reads `lint-paths` relative to the Python folder, as the rendered recipe (`[working-directory]`) and the commit hook run ruff: `src` is `backend/src`, `../.a2kay/jobs` is `.a2kay/jobs`, `.` is `backend/` only; the remediation names entries in that form. A repo with the Python stack at the root reads the same as before.
- **`gate.recipe-shadowing` no longer returns not checked when a rendered part needs a recipe of another part** (shelf-1r07: `generated-ui-css: ui-install`): the parts are dumped together through one temporary justfile (the repo is not touched).
- Corpus diff against 0.19.0 (42 repos): no verdict moved. No corpus repo has its Python stack in a folder, so the folder-reading changes are covered by the fixture tests (Python in `backend/`, node in `frontend/`), not the corpus.

## 0.19.0

- **Root `blueprint.toml`** (ADR 0034): a repo's blueprint config (waivers, overrides, `[[edge]]`, classification) may live in `blueprint.toml` at the root, the one home for a multi-stack repo; `docs/blueprint/blueprint.toml` is still read, and both files at once is a problem naming the `git mv`. Each stack's own `[tool.*]` stays in its manifest. `stack.tool-pins` reads `rust-just` only from the root `pyproject.toml`: with the Python stack in `backend/` just must be pinned in mise.toml (ADR 0023 amended).
- **Repo layout (ADR 0034, shelf-e722).** New row `layout.stacks-in-own-folders` (waivable, ADR 0018): with two code bases (language stacks; `node-tooling` is a tool; a stack deeper than one folder or hidden is no code base of the repo) each lives in `backend/` or `frontend/`; a code base at the root or in another folder fails and the remedy names the `git mv`. Corpus diff against the pre-change engine (42 repos): the row is the only change; it fails a2kay and full-stack-fastapi-template (both have Python and node at the root or in `ui/`), passes 32, not applicable 8 (no code base).
- **Stack roots.** The Python stack is detected at the root or in the one folder below it that holds a `pyproject.toml` (a root manifest wins; `packages`, `tests`, `fixtures`, `examples`, `docs` and dependency folders never count; two such folders are no backend). `Profile.stack_roots` now holds the Python stack's folder too; `Context.py(name)` and `Context.py_folder()` read its files. The python-uv profile's paths use `{py}`; every row (`ruff-selects`, coverage, floors, python-pin, uv-version, tool-pins, cli-help, shelf-sources, uv-tool, the clean-clone `uv sync`) reads the Python folder. A single-stack repo's rows, evidence and rendered parts are byte-identical to before.
- **Render per stack root.** With the Python stack in a folder, `.blueprint/python.just` recipes carry `[working-directory('backend')]` and every other `uv run` in the rendered parts becomes `uv run --project backend`; `.blueprint/step-inputs.toml` scopes `lint-changed`, `typecheck`, `deps`, `arch` and `test` to `backend/*` (a frontend edit starts none of them; a repo widens in `gate-inputs.toml`; root documents lose the `lint-changed` spell-check unless widened). `gate_py.changed` asks `any_gate changed` from the git top level for a folder below it (asked from `backend/` it reported no changed file and passed); the guard, preset-drift and the commit hook read `backend/pyproject.toml`; `gate_py.manifest(repo)` is the one reader of the Python stack's `pyproject.toml`.

## 0.18.0

- One `lint-paths` reading (`gate_py.norm`, `gate_py.under`) for `lint-changed`'s globs, the commit hook and `gate.lint-paths-cover-python`: `.`, `./src` and `src/` no longer build globs that match nothing (lint-changed said "skipped lint: no Python file changed" forever; the hook never linted).
- `[tool.blueprint.test.units]` `reads` globs ending in `**` key every file below the folder (on Python 3.12 `glob("dir/**")` matches folders only).
- Step output carries `gate-note: <text>` lines (the protocol of `any_gate.note`; blueprint writes the line itself, it does not import any-gate): `lint`/`lint-changed` note the file count, `deps` the packages reached of all.

- `secret_scan range` scans every untracked file in one gitleaks process (a temp copy; findings keep the file's own path), not one process per file.

- Commit hook (`blueprint gate hook`): a git failure reading the index now fails the hook (exit 2) instead of skipping ruff and the preset check and passing; the rendered entry is `uv run --frozen blueprint gate hook` (no re-resolve per commit, as the old ruff hooks had). With no `lint-paths` every staged `.py` is still linted (documented).

- Corpus diff against 0.17.0 (42 repos): 24 Makefile-only repos moved passing -> not set up on the gate-reading rows (`gate.one-command`, `gate.recipe-calls`; four more rows not applicable -> not set up), 3 more were already failing; the 15 justfile repos did not move on any old row except `stack.python-uv.linter` on homelab (passing -> not set up: its `ignore` holds `C901`, which cancels the `C90` complexity selection; the row now parses the ruff TOML instead of matching text). New rows: `gate.no-audit-leftovers` fails 5 repos (those tracking `checkpoints.txt` or a report; `blueprint gate clean-reports` fixes each), `gate.lint-paths-cover-python` fails a2kay.

- `test_a_second_run_starts_no_test_process` is marked `slow` with a reason (shelf-q40b): three real gate runs, 11 s alone, over the 3.5 s rule; it runs in `check` when the suite's key changed and always in `check-all`.
- `secret_scan range` with no upstream (shelf-fycm) starts at the merge-base with the default branch (`origin/HEAD`, `origin/main`, `origin/master`, `main`, `master`; never HEAD's own branch), or covers HEAD's own history on the default branch itself: it no longer scans every ref of the shared git dir, so a sibling worktree's unpushed fixture fails nobody else. Uncommitted work is scanned in that case too. `full` (`secrets-all`) still scans every ref.
- **Waivers replace the baseline (ADR 0018, shelf-86uh).** `[[tool.blueprint.waivers]]` (`id`, `reason`, `since`, `until`: `until` at most 90 days after `since` and 90 days out, so a renewal cannot run forever; keep the first `since`) in `docs/blueprint/blueprint.toml` or `pyproject.toml` is the only way to wait on a checkpoint: a waived row passes with its days left and shows as a `waiver` notice; an expired, reasonless, dateless, `since`-less, over-90-days or unknown-id waiver fails the run (the row keeps its real verdict). A TOML datetime `until` counts by its day (it used to raise `TypeError`). A waiver cannot excuse `not checked` (the audit could not judge; the row stays and says the waiver was ignored). A waiver on a row that passes without it, and waivers in a TOML file the audit does not read, are named in notices. The engine no longer reads `docs/blueprint/checkpoints.txt`, no row is "new since the last audit" (`Row.new`, `runner.ACCEPTED` and the 🆕 gate line are gone), and `check --write` writes nothing tracked. **A new checkpoint now fails right after a pin bump.** A repo that ever ran an audit tracks `docs/blueprint/checkpoints.txt`, so `gate.no-audit-leftovers` turns it red on this bump until `blueprint gate clean-reports`; a repo that kept a list hiding new rows now fails on them.
- `gate.no-audit-leftovers` (shelf-cni5): fails while `docs/blueprint/checkpoints.txt` or a Markdown report (first line `# Blueprint`) is tracked; the fix is one command, `blueprint gate clean-reports` (`git rm` of exactly those files, printing each; commit the result).
- `gate.lint-paths-cover-python` (shelf-pv71): when `[tool.blueprint.gate] lint-paths` is set, every tracked `.py` must sit under one of them; else the row names the unlinted folders.
- `stack.python-uv.linter` (shelf-pv71) parses the ruff lint table (`.ruff.toml`, `ruff.toml`, then `pyproject.toml`) instead of matching text: `S` and `C90` (or `ALL`) must be selected (`select`, `extend-select`) and not ignored, so `ignore = ["S"]` fails.
- `[wide]` and `[narrow]` reasons in `gate-inputs.toml` that are only a placeholder (`todo`, `tbd`, `n/a`, `none`, a repeated word or character) fail (shelf-pv71).
- `stack.compose.dependencies` (shelf-0lv1) passes when the rendered `images` step runs `blueprint.compose_pins` (`image-pins = true`). Hook decision: no per-commit compose hook; the digest rule runs in `just check`, which pre-push runs (ADR 0027), and a second copy at commit would only repeat it.
- A Makefile-only repo's gate-reading rows (`gate.step-inputs`, `gate.wide-inputs-have-a-reason`, `gate.runs-blueprint`, `gate.guards-have-red-tests`, `gate.checkers-wired`, `gate.recipe-calls`) report "not set up because the gate is unreadable" instead of "not applicable"; a justfile that will not dump reports "not checked ... unreadable". A repo with no gate at all is unchanged.

- The python `deps` recipe checks only the packages the change reaches (`any_gate_python packages`; every package where the adapter is absent); `deps-all` is every package and the release gate (`check-all`) runs it.

- **`blueprint gate hook`** (shelf-3rm8): one commit-hook process runs the secret scan, the guard, preset drift (when pyproject.toml is staged) and ruff check and format over the staged files, so a commit starts one `uv run` instead of five. The pre-commit template has one `blueprint-hook`; the python-uv `hooks` row and `secrets.scanner` accept it.
- **Breaking: go and rust profiles removed** (shelf-rofp): no consumer used them. A `go.mod` or `Cargo.toml` still makes a stack, so `stack.<go|rust>.profile` fails with "no profile: the code is unjudged" instead of the repo going quiet. **Makefile support removed:** no profile row looks for a Makefile and `gate_graph` no longer parses one; a Makefile-only repo still fails `gate.runner` (its evidence now names `blueprint init`), and its sibling gate rows now read "not set up: gate unreadable". `node-tooling` now extends `node` (`extends = "node"` in a profile file: the base's roles, with its own rows replacing the same-named ones).
- **`check --write` writes the reports to `.blueprint/reports/`** (a self-ignoring folder), not `docs/blueprint/`; nothing tracked is written (shelf-rabg). **`blueprint init` writes `policy/compose.rego` only for a deployed repo.**
- Unit `paths` take globs (`tests/test_*.py`), and a unit may be `rest = true`: it owns every test file and folder under the test roots that no other unit claims (a new test file joins it; it is no unit when nothing is left; one per repo). Both expand when the settings are read, so keys, plan and runner see concrete sorted paths and a globbed unit has the key of the hand-listed one. a2kay's 70-line `root` unit becomes `rest = true`.
- Slow tests in `check` (shelf-nqal): with `marks` leaving `slow` out (`not slow`), `gate test` runs a second `-m slow` pass over the suites, each under its own key in a separate receipts file (`slow-<receipts>`, `gate-receipts-slow.json` in the shared git directory), so a suite's slow tests run when its key changed since they last passed and not for a docs-only change; a suite with no slow test is fine (pytest exit 5), `unit_runner --only` keeps no coverage data. `test-all` and override runs do not run it. A repo whose suites have no key (a bare `tests` folder) still runs slow tests only in `check-all`.
- Unit keys are computed once per `gate test` run (shelf-8r18): `gate_units.keys` reads each file once and parses it from the same bytes (it was parsed twice and read a third time, and every unit's key was recomputed by the cache check, the plan and `combine`). The keys go to the unit runner as `--keys`; `combine` is skipped when the repo declares no floor. Keys are byte-identical to 0.17.0's (a golden test, and a2kay's nine keys compared old against new). a2kay's key code: 22,509 file opens a no-op run before, 862 after.
- One test path (shelf-m0xw, absorbs shelf-nvj1): `blueprint gate test-all` is `gate test` over every suite (`any_gate_python plan --all`) and every mark, receipts ignored (blank keys), `randomize` honoured; `gate_py.test_all_command` is deleted. A floor applies only when the repo declares one (`[tool.blueprint.test] floor`, else `[tool.coverage.report] fail_under`): the built-in 65 is gone. A repo with `-p no:cov` in `pytest-args` passes `check-all` (the old path passed `--cov` and pytest exited 4); its floor is reported as not judged unless `coverage` mode measures it. Without `coverage` mode a declared floor is measured by pytest-cov across the stages (`--cov-append`) and one `coverage report --fail-under` judges it. `unit_runner --whole` runs every mark. Pytest arguments still make an override run: no receipts, no floor.

## 0.17.0

- Corpus diff against 0.16.0: 42 repos, no verdict moved (the new rows only turn a warning into a pass where a repo's gate runs codespell through `blueprint gate lint`).
- `stack.compose.spelling`, `stack.node.spelling`, `stack.node.hooks` (and the node-tooling twins) accept `blueprint gate lint|spell` as codespell (a2kay's gate runs codespell only through `lint-changed`; its justfile never says the word); a repo with no spelling check still fails (shelf-ab0f).
- `[tool.blueprint.gate] image-pins = true` also pins compose images: `images` runs `python -m blueprint.compose_pins`, one process over every tracked compose file, failing an `image:` that is not `name:tag@sha256:<64 hex>`; `image-pin-exempt = ["<prefix>"]` excuses an image whose text starts with the prefix (an image built from the same commit). A repo drops its own `compose-pins` (shelf-8p76).
- A `[[tool.blueprint.gate.generated]]` entry may name `needs = ["recipe"]`: rendered as just dependencies of `generated-<name>` (a private recipe works), so the command need not call the recipe itself (shelf-mgno).

## 0.16.0

- Corpus diff against 0.15.0 (42 repos): no verdict moved to worse except `stack.compose.spelling` on yosefactory (not set up -> warning): it configures `[tool.codespell]`, which the row now recognises, and its Makefile gate is not read (already `gate.runner`). New row `gate.narrowed-inputs-have-a-reason` and the optional `stack.dockerfile.dependencies` read not applicable on every repo that does not use them.
- `agents.worktrees-in-sync` (v3, shelf-tpq2): a worktree in the middle of merging main (MERGE_HEAD exists) is not held for the commits it is taking; the evidence now names the fix per line, `merge main: git merge origin/main` for being behind and `land it into main` for unmerged work (a2kay stayed red on this row: 22 ahead, 2 behind, and the message did not say which fix applied). Unmerged work still fails during a merge of main.

- Test standard (shelf-4wj3): a test marked `slow` is skipped by `check` (`[tool.blueprint.test] marks = "not slow"`) and run by `check-all`: `test-all` no longer applies `marks` (it used to skip them too). `just test` and `just test-all` take pytest's arguments (`just test-all -m slow`, `just test -k name`; `blueprint gate test|test-all -- <pytest args>`); an override run writes no receipt (the plan's keys are dropped), and `test-all` with arguments turns the coverage floor off. Docs: testing.md "Slow tests". A repo whose addopts excluded slow tests from `check-all` moves the exclusion to `marks`.
- Generated files are current (shelf-4wj3): `[[tool.blueprint.gate.generated]]` (name, command with `{out}`, outputs, optional reads) renders `.blueprint/generated.just` with one `generated-<name>` step each, run as `python -m blueprint.generated <name>`: the generator writes into a temp folder and the outputs must equal the committed files (differs, missing, left over; exit 2 when the generator fails). Default inputs: outputs, reads and pyproject, or `*` with no reads.

- `images` step (shelf-vdzh): a repo that tracks a Dockerfile or a compose file renders `.blueprint/images.just` and `check` runs `images`: hadolint, dockerfmt and `docker build --check` per Dockerfile; dclint (`--max-warnings 0`), yamlfmt (`-lint`) and Compose's `config --no-interpolate -q` per compose file; a missing tool is named (exit 2). Default inputs: the image files, their configs and mise.*. The digest-pin check is no longer required: `stack.dockerfile.dependencies` is an optional row (a new profile key `optional = true`: not set up reads not applicable, set up but not run still fails), and `[tool.blueprint.gate] image-pins = true` (with `image-pin-contexts`) makes `images` run `python -m blueprint.recipes.check_dockerfile_pins`, so a repo deletes its copy of the script. The dockerfile and compose rows read `.blueprint/images.just` as well as the justfile. A repo with a hand-written `images` recipe deletes it and re-renders, or declares an `[[override]]`. Compose digest pinning (a2kay's `compose-check` image rule) is not rendered: it stays the repo's own.

- `stack.node.spelling`, `stack.node-tooling.spelling` and `stack.compose.spelling` accept codespell (a `.codespellrc` or `[tool.codespell]`, run by the gate) as well as typos; `stack.node.hooks` and `stack.node-tooling.hooks` accept codespell in `.pre-commit-config.yaml`. Typos is no longer required (shelf-rw8k).
- python.just renders `arch` (`uv run lint-imports`) and `check` runs it when the repo declares import-linter contracts (`[tool.importlinter]` in pyproject.toml or `.importlinter`); default inputs python files, pyproject, uv.lock. A repo with its own `arch` recipe renames it (a2kay: `archlint` -> `arch` by deleting its own and re-rendering) or declares an `[[override]]`; a step named by both the stack and `[tool.blueprint.gate] steps` runs once.

- Node step set (shelf-3ht9): a node folder with a lockfile renders `.blueprint/node.just`: `ui-install` (private, one `mkdir` lock so parallel steps install once, `npm ci`/`pnpm install --frozen-lockfile`/`yarn install --immutable` by lockfile) and, for each tool whose config the folder commits, `ui-lint` (biome.json: `biome ci --error-on-warnings .`), `ui-types` (tsconfig.json: `tsc --noEmit`), `ui-deps` (knip.json or `"knip"` in package.json: `knip`), `ui-arch` (.dependency-cruiser.*: `depcruise src|*.js`), `ui-test` (vitest in package.json: `vitest run [--coverage]`). Default inputs `<folder>/*` and `mise.*`. One folder gets the set (the first with a lockfile). The `stack.node.*` rows accept the rendered recipes (tested). A repo with hand-written `ui-*` recipes must delete them and re-render, or declare an `[[override]]`.

- Step input defaults (shelf-9hne): the blueprint owns each known step's input globs per stack and renders them to `.blueprint/step-inputs.toml` (typecheck, deps, arch: python files, pyproject, uv.lock; scripts: `*.sh`, `.shellcheckrc`; blueprint, secrets, lint-changed, test: `*` with the reason). The repo's `gate-inputs.toml` holds only exceptions: a list widens a default, a step of its own declares its globs, `[narrow] <step> = "<why>"` replaces a default. `gate.step-inputs` now passes a repo with no `gate-inputs.toml` when every step has a default; new row `gate.narrowed-inputs-have-a-reason`. A repo re-renders and deletes the keys that equal a default and the `[wide]` entries of default-wide steps (a stale `[wide]` entry still fails).

## 0.15.0

- The gate has fewer steps. `blueprint` now runs the commit guard, the linter preset check, the render check and the audit in one process (`blueprint gate blueprint`); `lint-changed` (and `lint`) also run codespell; the standard list drops `guard`, `preset`, `render` and `spell-changed` (their recipes stay for hooks and humans). A consumer's `gate-inputs.toml` keys for dropped steps match nothing (an unkeyed step always runs); re-key `lint-changed` to `*` and `blueprint` to `*`. `gate.runs-blueprint` accepts `blueprint gate blueprint`; the python-uv spelling row accepts `blueprint gate lint`. Corpus diff against 0.14.2: no `passing -> failing`; the moves are the linter/tests rows below and `gate.wide-inputs-have-a-reason` on a2kay (absent -> failing: its six `*` steps need `[wide]` entries).
- The steps runner (any-gate 0.5.0): SIGTERM and SIGHUP stop every step's tree; a step the gate stopped is a flag, not exit 125; a crashed step is a failed step; `GATE_FAIL_FAST`; a clean tree no gate has passed runs every declared step once.

- `gate.wide-inputs-have-a-reason` (new, warns until the next audit): a step declared `["*"]` in gate-inputs.toml needs a `[wide]` entry `<step> = "<kind>: <why>"`, kind one of change-set, self-keyed, reads-everything, outside-files. It does not guess what a recipe reads.
- The audit reads the justfile once per run (a2kay: 30 processes and 2.4 s became 20 and 1.8 s); the steps runner shows a failure as it lands and takes `--fail-fast` and `--step-limit` (any-gate 0.4.0).

- Test doubles: `Repo.env` drops the developer's `BLUEPRINT_TIMEOUT`, and `gate_py._lease_installed` is the one seam where the machine's `any_lease` changes the release run's command (both shapes tested).

- `agents.worktrees-in-sync` ignores the age of unmerged work while prek runs the pre-push hooks (`PRE_COMMIT_TO_REF` set): the push is the step that lands it, and the row used to refuse that push. Being behind main still fails. An ordinary audit is unchanged.

- `[tool.blueprint.test] randomize = true`: `blueprint gate test-all` (the release run) passes `-p randomly`; `check` does not. The repo keeps `-p no:randomly` in `addopts`.

- python-uv `tests` row also requires `filterwarnings` in `pyproject.toml` (`["error", ...]`: a leaked process, file or stream fails the test that made it). The `linter` row requires the bandit (`S`) and complexity (`C90`) rules, by name or through `ALL`. Both warn until the next audit (ADR 0018). Corpus diff against 0.14.2: 7 of 42 repos move to not set up (a2kay tests; a2skill, a2web, iorlas-task-loop, mcp-gateway, mempalace, yosefactory linter).

## 0.14.2

- Snapshot also carries any-gate (the test-slot waiter names a hung holder's pid and age, repeats every 5 minutes) and the any-knowledge `working-with-agents` template (delivery scope for multi-ticket work).

- `blueprint check --brief` (what `just blueprint` prints) clips evidence to 200 and the fix to 240 characters, and says when it cut; the full text stays in `blueprint check`. A not-set-up standard row was ~1 KB each.

- Dead code removed (`LAYERS`, `OUTCOMES`, `_LINT_BEAD`, `CALLS_ID`); `render` uses `gate_graph.JUSTFILES`. No behaviour change.
- python-uv `tests` row also requires `--strict-markers` in pytest `addopts` (a marker typo fails instead of selecting nothing). New row: warns until the next audit (ADR 0018).
- `blueprint.testing`: `run_cli` runs the engine in-process (no interpreter start per call); `Repo.git` turns commit and tag signing off so a developer's global config cannot hang a throwaway repo.
- `hooks.pre-push-is-the-gate` accepts a `git lfs push` hook (prek replaces LFS's own pre-push hook) and a hook that runs a `bash <script>.sh` whose script runs `just check`.
- `gate.no-ci` takes a per-workflow `[[override]] id = "gate.no-ci"` (scope, reason, expiry): no CI stays the default, a repo that needs one says so (ADR 0027 amended).

## 0.14.1

- Version files corrected: tag `blueprint-v0.14.0` was cut on a commit whose `pyproject.toml` still said 0.13.2 (0.13.1 and 0.13.2 had been released meanwhile). The code in `blueprint-v0.14.0` is the 0.14.0 content below; pin `blueprint-v0.14.1`, which carries it with the right version.

- The mcp framework rows (`build`, `tests`, `surface-integrity`) accept `blueprint gate test` as running pytest, so a repo on the standard rendered test step no longer fails them.

## 0.14.0

- **A comment or a message naming a tool no longer counts as running it**: the gate text the stack rows read drops comment lines and the text of `echo`/`printf` lines (a command chained after them still counts). Before, `# ruff check .` or `echo "docker build -f Dockerfile ."` passed the linter and Dockerfile-tests rows.
- `stack.roles` version 5: the python-uv `tests` role also needs `pytest-timeout` in the dependencies and `timeout = <seconds>` in `[tool.pytest.ini_options]` (a hung test fails the run; no repository has CI to kill it). It warns until the next audit (ADR 0018).
- Editor and interpreter litter (`.DS_Store`, `.pyc`, `.swp`) beside reached code no longer changes a test unit's key. The rendered `deps` recipe hands package folders to `xargs` NUL-separated.
- `agents.worktrees-in-sync` and `agents.other-worktrees` compare against `origin/main` when it exists (a clone's local `main` goes stale beside worktrees), else `main`.
- `lint` and `spell` (whole-repo linters) render without `release-gate`; only the release recipes are opt-in.
- Units under `pytest-cov` run with `--cov-fail-under=0`: the floor is applied once, to the combined data.
## 0.13.2

- Snapshot only, no blueprint change: carries git-porcelain 0.31.0 (`take_branch`/`restart_branch` `track=`, `BranchTaken.upstream`).

## 0.13.1

- Snapshot only, no blueprint change: carries any-agent 0.23.0 (`Harness.effort_levels`, `Summary.res["tokens"]["reasoning"]`).

## 0.13.0

- Node coverage floors and alternatives are judged in the node project's folder (`ui/`), not the repo root; the coverage config accepts any `vitest.config.*` extension.
- Python stack rows recognize pinned Ruff commands through `uv tool run` and `uvx`; mixed-stack tests verify `node-tooling` edges.
- Gate tests refuse invalid or unowned units; CLI-filtered runs cannot populate plain-run coverage caches. Keys include external test
  configuration and test package initializers. Recipe checks resolve imported/defaulted recipes and quoted or continued calls; Node
  installs use the detected folder and its lockfile. Lint preserves the first failure, including signal exits, while running both tools.
- Release recipes render only with `[tool.blueprint.gate] release-gate = true`; measured test units can enforce their floor inside `check`.
- Rendered `tools` installs Node dependencies after mise in the detected folder, using npm, pnpm or yarn only with its lockfile.
- `[tool.blueprint.test]` `pytest-args`, `marks` and `env` configure every test run and invalidate every unit's cached key.
- The `python-uv` stack accepts `ruff.toml` / `.ruff.toml` and `pyrefly.toml`, preserving lint-table and strict-preset requirements.
- `gate test-all` uses `[tool.coverage.report] fail_under` when `[tool.blueprint.test] floor` is unset, before falling back to 65.
- **Test units for a repo that is not a workspace**: `[tool.blueprint.test]` units, keys from the import graph, per-unit coverage data cached and combined before the floor (`coverage run` or pytest-cov). `gate_test.run`'s `pytest_args` defaults to none with coverage.
- New rows: `gate.recipe-shadowing`, `gate.recipe-calls`, `agents.other-worktrees` (audit-only). `agents.worktrees-in-sync` (version 2) judges this worktree only.
- New stack `node-tooling` for a build-tool-only `package.json`.
- **The python steps are engine commands**: `blueprint gate lint|format|spell|test-all`, with `lint-changed` and `spell-changed` in `check`; a repo's paths, extra steps and floor are data in `[tool.blueprint.gate]` and `[tool.blueprint.test]`, so it defines no recipe of its own. `check-all` runs `check-extra`. `stack.roles` is version 4.
- `stack.dockerfile.tests` needs a `docker build` line naming the path (`--check` counts). `gate.clean-clone` shows the failing step and 20 lines of its log. See ADR 0033.

## 0.12.0

- `blueprint` opts in to the public-`Any` rule: each remaining `Any` in a public signature is parsed TOML and says so. `check_dockerfile_pins` and `testing` bound their git calls with `timeout=` (a git timeout in the recipe falls back to the file walk).

## 0.11.0

- `gate.clean-clone` points mise at the injected env's `HOME` (`$HOME/.config/mise`), not the process home.

## 0.10.0

- **Breaking: `secret_scan.scan(repo, mode)` and `Mode` are gone.** `scan_staged(repo)`, `scan_range(repo)` and `scan_full(repo)` are the three scans; `python -m blueprint.secret_scan staged|range|full` is unchanged.
- `stack.shelf-sources` fails mixed shelf tags/spellings and re-pinning overrides; `init` normalizes them.
- Gate steps declare their inputs (`gate-inputs.toml`); an unaffected step is not started; new `gate.step-inputs` audit row. `stack.agent-cli-pins` added.
- The knowledge, ADR and agent-docs checks moved to the `any-knowledge` package.

## 0.8.0

- **Breaking: `runner.run` lost its `audit` flag.** `run(...)` is the per-commit gate, `run_audit(...)` also runs the audit-only checks (the CLI picks one by `--audit`). What is checked and rendered is unchanged.
- **Breaking: `report.write` lost its `prune` flag.** `write(...)` prunes the reports of a concern the run no longer has, `write_concern(...)` (a one-concern run) leaves the others. Written files are unchanged.
- Test helper `Repo.write(..., executable=True)` is now `Repo.write_executable(...)`.
- Every text read and write carries `encoding="utf-8"`; every `errors="replace"` carries a `# lossy-ok:` marker; globs that feed output are wrapped in `sorted()`. No output changes on a UTF-8 machine.
- `secret_scan` and `guard`: every child process has a timeout (a hang is `ScanError`, or exit 2 for the guard, never a pass); `secret_scan` no longer reads `os.environ` or calls `shutil.which` (a missing gitleaks is the same `ScanError` message).
- Left alone on purpose: the engine is stdlib only (it runs from a bare clone on `PYTHONPATH`, README), so it does not use stream-proc, child-env, content-digest or any-clock.
