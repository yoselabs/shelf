# Checkpoint review (task 1)

For the owner. Nothing here is cut; each verdict is a proposal. Measured 2026-11-20 on this repo, warm cache, one process:
`blueprint check --repo . --json` = **1.75 s wall** (gate set), `--audit` = about 7.3 s summed per checkpoint. Per-checkpoint times
come from timing `runner._judge` for each active check (a throwaway script, not committed).

## What was counted

`blueprint checkpoints --json` lists **155** ids: 45 registered checks and 110 rows projected from the stack and framework profiles
(`stack.<stack>.<role>`, `framework.<name>.<role>`). 24 of the 110 are `na` or `untested` by construction. Eleven are `*.profile` rows.
Only 7 of the 155 take more than 50 ms; the rest cost nothing. **Cost is not the problem. Override upkeep and duplicated meaning are.**

## Who overrides or ignores what

Evidence is thin: of the consumers under `~/Workspaces`, only **a2kay** carries `docs/blueprint/blueprint.toml`. The shelf has one override
(`gate.ci`, ADR 0027). **task-loop and ogy have no blueprint state at all**: they never ran the audit, so "ignored" is inferred from
the proposal (task-loop ran affected-only tests as its own step and added gitleaks) and not measured. The `wt/` and `shelf-wt-*` folders are
shelf worktrees, not consumers.

a2kay's overrides, all in its `blueprint.toml`:

| id | why | decided by | expires |
|---|---|---|---|
| `stack.python-uv.coverage` | enforces `coverage report --fail-under=90`, not pytest-cov (shelf-2hl) | owner | **2026-11-11, expired 9 days ago** (task 10 checks what its gate says now) |
| `detection` x2 (two macOS shell scripts) | nothing in the gate can run them | owner | 2027-04-12 |
| `stack.python-uv.cli-parse` x2 | pre-parsers for global options only | **agent** | 2027-04-12 |
| `stack.python-uv.python-range` | onnxruntime has no CPython 3.15 wheel | owner | 2027-01-29 |

## The table

Gate = runs on every `just check` (`blueprint check --gate`). Audit = only with `--audit` (listed audit-only by the code).
Time = this repo, seconds, `-` = under 10 ms. Families with the same shape are one row.

| checkpoint(s) | run | time | overridden / ignored by | verdict |
|---|---|---|---|---|
| `stack.python-uv.cli-parse` | gate | 1.0 | a2kay x2, agent-decided | **cut.** Slowest gate check after python-pin, one of two to take real time, and the only consumer that met it overrode it twice. Proposal item 8 already lists it. |
| `stack.python-uv.coverage` (+ `tests`) | gate | - | a2kay (expired); task-loop ignored | **change, not keep** (task 3): outcome contract, tool-agnostic. Today it checks a flag name. |
| `stack.python-pin` | gate | 1.3 | none | **justify.** 75% of the whole gate run. Keep the rule, find what it spawns and make it cheap or audit-only. |
| `stack.python-uv.uv-tool` | gate | - | none | keep (applications only). |
| `stack.*.agent-guidance` (9) | gate | - | none | **cut.** `agents.culture-files` already requires every `docs/agents/` file the profile names. Same fact twice, two rows to override. |
| `stack.*.profile`, `framework.*.profile` (11) | gate | - | none | **cut as rows.** Each says "a profile exists for X". Becomes one failure when detection finds a stack with no profile (design D4); a pass row for it is noise. |
| `stack.*.hooks` (9) | gate | - | none | **justify.** Overlaps `gate.hooks-recipe` and D6's anti-pattern checks. Merge into D6 or say what the per-stack row catches that those do not. |
| `stack.*.{formatter,linter,types,spelling,dependencies,toolchain,tests,architecture}` | gate | - | none (a2kay passes all 20) | keep. These are the contract. 24 `na`/`untested` rows among all derived rows: show them only in the audit report, never as checkpoints. |
| `stack.*.coverage` for compose, dockerfile, nix, shell | gate | - | none | **cut.** 4 of 6 are `na` by construction; a row that can never apply is listing noise. |
| `framework.*.ci` (3), `framework.*.embedded-script-lint` (3) | gate | - | none | **cut.** All six are `na` or `untested: TBD`. A checkpoint with no test is a wish. Add back with a tool. |
| `framework.mcp.*`, `framework.godot.*`, `framework.unity.*` rest | gate | - | none (a2kay's mcp rows all pass) | keep for mcp. **justify godot and unity**: no repo under `~/Workspaces` uses them; they are profile-only and unproven. |
| `stack.dockerfile.ship-smoke`, `ship-updater` | gate | - | none | keep (purpose-gated, ADR 0026). |
| `stack.roles`, `framework.roles` | gate | - | none | keep (the projector). |
| `stack.tool-pins` | gate | 0.05 | none | keep. |
| `stack.shell-strict` | gate | - | none | keep. |
| `stack.tools-installed` | audit | 0.09 | none | keep, audit. Machine state, not repo state. |
| `agents.instructions`, `managed-block`, `culture-files`, `session-hooks` | gate | - | none | keep. |
| `agents.worktrees` | gate | 0.04 | none | keep. |
| `agents.worktrees-in-sync` | audit | 0.40 | none | keep, audit. |
| `agents.pocock-skills` | gate | - | none | **cut.** Demands one author's third-party skill pack in every repo. A taste, not an outcome; no consumer has it as a requirement of its own. |
| `agents.bd-metrics-off` | gate | - | none | **justify.** One env var; beads-only. Keep only if bd metrics cost something real; say what. |
| `backlog.tracker` | gate | - | none | keep. |
| `backlog.{lock-ignored,no-local-override,no-tracked-export,no-tracker-file,hooks-spare-beads}` | gate | -, 5 rows | none | **justify, merge to one `backlog.config` row.** Five rows to override for one tool's config hygiene. |
| `backlog.strict-config` | audit | 0.43 | none | keep, audit. |
| `backlog.lint` | audit | 1.9 | none | keep, audit. `just check` already runs `beads-lint`, so a per-commit copy would be a duplicate. |
| `gate.one-command`, `runner`, `runs-blueprint`, `checkers-wired`, `guards-have-red-tests` | gate | - | none | keep. This is what makes a gate a gate. |
| `gate.hooks-recipe` | gate | - | none | keep. |
| `gate.hooks-installed` | audit | - | none | keep, audit. |
| `gate.ci`, `gate.ci-no-manifest-edit` | gate | - | shelf overrides `gate.ci` (ADR 0027, no CI) | **change.** A repo with no CI should be `na`, not an override. The ADR then needs no per-repo override row. |
| `gate.ci-green` | audit | - | none | keep, audit; same `na` rule. |
| `gate.clean-clone` | audit | 0.6 here; a2kay recorded 125-153 s | a2kay sets its own budget | keep, audit only. The only checkpoint whose cost is real: a full gate run in a fresh clone. Never per-commit. |
| `gate.default-branch` | audit | - | none | **justify.** "default branch is `main`" is a taste; if kept, why does it matter to the gate? |
| `gate.git-remote`, `git-config-clean` | audit | - | none | keep, audit. |
| `gate.lfs-binaries`, `lfs-installed` | gate, audit | - | none | keep (applies only where LFS is in use). |
| `knowledge.adr-format`, `adr-index`, `glossary` | gate | - | none | keep. |
| `secrets.encrypted`, `rule-coverage` | gate | 0.01 | none (`na` in the shelf, no sops) | keep. They say nothing about plaintext secrets; task 6 adds that. |

## Count if every proposed cut is accepted

Cut: `cli-parse` (1), `*.agent-guidance` (9), `*.profile` rows (11), compose/dockerfile/nix/shell `coverage` (4), framework `ci` and
`embedded-script-lint` (6), `agents.pocock-skills` (1). **32 of 155.** Merge: 5 backlog rows into 1 (-4). Change: `coverage`/`tests`
(task 3), `gate.ci*` become `na` without CI. Justify (owner to answer): `python-pin` time, `stack.*.hooks`, godot/unity, `bd-metrics-off`,
`default-branch`.

## Open facts this review could not settle

- task-loop and ogy ran no audit, so what they "ignore" cannot be read from files; only a2kay's overrides are fact.
- Time was measured on the shelf, a Python repo with no LFS/compose/dotnet; other stacks' `stack.*` rows are known cheap (file reads)
  but their real cost is the gate steps they require, not blueprint.
- Which checkpoints a2kay's gate fails today is task 10, not here.

## Applied 2026-11-20 (owner: "apply the cuts")

Done: `stack.python-uv.cli-parse` (the lenient-parsing row; `cli-help-tested` stays); `agents.pocock-skills`; the nine
`*.agent-guidance` rows; `stack.{compose,dockerfile,nix,shell}.coverage`; `framework.{godot,unity,mcp}.ci` and `embedded-script-lint`.
That is 1 + 1 + 9 + 4 + 6 = 21 rows. The profile files keep the role data; `is_checkpoint` in `concerns/stack.py` decides which roles project a row.

**Not applied, with the reason:**
- The 11 `*.profile` rows. The review said they restate that a profile exists; in fact they carry the *detection evidence* (the file or folder that set
  the stack or framework, the framework root). 23 tests and the report read it. Cutting needs that evidence moved to the report header first.
- `stack.*.hooks` and godot/unity (marked "justify", owner's answer needed), `python-pin` speed, `bd-metrics-off`, `default-branch`: "justify", not "cut".
- The backlog merge (5 rows into 1) and the `gate.ci*` become-`na` change: they change behaviour, not just remove rows; left for their own beads.
- The `untested` mechanism (a role the profile marks `untested` becomes a blueprint gap) now has no profile exercising it, so its test was
  replaced; the code stays.

a2kay's two `cli-parse` overrides now excuse nothing; the run's unused-override notice will say so.
