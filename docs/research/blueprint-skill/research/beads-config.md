# beads (bd) configuration: every key, strict settings

**One pass, 2026-10-10.** bd 1.1.2 (Homebrew), embedded Dolt. Sources: `bd help`, `bd config --help`,
`docs/CONFIG.md`, and the v1.1.2 source tag (`internal/config/{config,yaml_config}.go`, `cmd/bd/*`).
Experiments ran in a throwaway repo (`bd init --prefix t`). Nothing was written to shelf or to
`~/.config/bd/config.yaml` (shasum checked before and after: unchanged).

Evidence labels: **exp** = tested by experiment · **src** = read in v1.1.2 source · **doc** = docs only ·
**dead** = key is defined, but nothing in 1.1.2 reads it (no consumer outside defaults or the yaml-only list).

Scopes:
- **yaml**: `.beads/config.yaml`, committed. `bd config set` prints `(in config.yaml)`. Keys under the
  prefixes `validation. hierarchy. routing. sync. git. backup. export. dolt. federation. ai. metrics. directory. repos. external_projects.` all go here.
- **db**: Dolt `config` table. `bd config set` prints no location. It is pushed with the Dolt remote.
- **user**: `~/.config/bd/config.yaml`, per machine.
- **git**: `.git/config`, per clone.
- **meta**: `.beads/metadata.json`.

Precedence, lowest to highest: `~/.beads/config.yaml` → `~/.config/bd/config.yaml` → `.beads/config.yaml` →
`$BEADS_DIR/config.yaml` → `.beads/config.local.yaml` → `BD_*` env vars → flags.

## Keys

| Key | Scope | Values | What it does (evidence) | Strict value | Why |
|---|---|---|---|---|---|
| `validation.on-create` | yaml | none/warn/error | On create, checks the description for the sections the type requires. bug: Steps to Reproduce + Acceptance Criteria. task/feature/story: Acceptance Criteria. epic: Success Criteria. decision: Decision + Rationale + Alternatives Considered. spike: Goal + Findings. chore/milestone/custom types: nothing. A non-empty `--acceptance` field counts as the AC section. The match is a case-insensitive substring. (exp) | `error` | The only real content gate in bd. |
| `validation.on-close` | yaml | none/warn/error | Checks `bd close`. The only rules: the reason is not empty, is not "closed", and is at least 20 characters. It does not look at AC. `bd update -s closed` skips the check entirely (the issue closed with `close_reason=None`). (exp) | `error` | Cheap. Weak; see gaps. |
| `validation.on-sync` | yaml | none/warn/error | **dead**: only a default is set, no code path reads it. (src) | `error` | Inert today. Set it so the check is on if a later release wires it up. |
| `validation.metadata.mode` + `validation.metadata.fields.<k>.{type,values,required,min,max}` | yaml | mode: none/warn/error. type: string/int/float/bool/enum | Checks metadata JSON on create, `--metadata`, `--set-metadata` and `--unset-metadata`. Rejects bad enum values, out-of-range ints, and a missing `required` field. Unknown keys pass. One schema covers every type. (exp) | `error`, typed optional `branch`/`commit` (string) | Matches shelf's provenance convention. `required: true` would block every type, gates and wisps included, so don't use it. |
| `create.require-description` | yaml | bool | `bd create` with no description fails. Not checked on update. (exp) | `true` | |
| `hierarchy.max-depth` | yaml | int ≥1 (0 rejected) | **dead**: `CheckHierarchyDepth` has no callers. `t-x.1.1` was created with max-depth=1. (exp+src) | `2` (inert) | Records the intent. The doctor script has to enforce it. |
| `sync.require_confirmation_on_mass_delete` | yaml | bool | **dead**: no consumer in 1.1.2. The docs say it prompts on `bd dolt push`. (src) | leave `false` | Inert. If it ever works it would be an interactive prompt, and that would stall agents. |
| `sync.remote` (`sync.git-remote` is deprecated) | yaml | URL | The Dolt remote, e.g. `git+https://…` (stored under `refs/dolt/data`). (doc) | set per repo | The off-machine copy. |
| `dolt.auto-commit` | yaml | on/off/batch | `on`: every write makes a Dolt commit and HEAD moves. `off`/`batch`: writes stay in the working set until the next commit. (exp) Flag help says the default is off; the real default is `on`. | `on` | Every change becomes history, and `bd dolt push` sends committed state only. |
| `dolt.auto-push` / `-interval` / `-timeout` | yaml | bool / 5m / 30s | Pushes after writes. The docs say it is opt-in because concurrent writers can corrupt the remote. (doc) | `false` | Parallel agents would race. |
| `dolt.shared-server`, `dolt.max-conns`, `dolt.debug`, `dolt.local-only`, `dolt.auto-start`, host/port | yaml | various | Server-mode plumbing; no effect in embedded mode. (src) | unset | |
| `backup.enabled` / `interval` | yaml | bool / 15m | After a write, at most once per interval, makes a Dolt-native backup in `.beads/backup/`. That directory is gitignored. (exp) | `false` | Same disk as the database, so no off-machine value. The Dolt remote is the backup. |
| `backup.git-push`, `backup.git-repo` | yaml | bool / path | **dead** (src). | unset | |
| `export.auto` | yaml | bool | After a write (throttled), exports JSONL to `.beads/<export.path>`. (exp) | `false` | The docs say it is not sync and not the source of truth. Turn on only if a viewer needs it. |
| `export.git-add` | yaml | bool | **Every bd write runs `git add .beads/issues.jsonl`** (exp). The pre-commit hook also re-exports and stages it whenever `.beads/` files are staged (src). | `false` | Puts tracker churn into unrelated commits. Shelf's index already had a staged `issues.jsonl` at session start. |
| `export.interval` | yaml | duration | Minimum gap between exports. `0` is quietly treated as 60s. (src) | default | |
| `export.path`, `import.path` | yaml | relative path | JSONL filenames. (doc) | default | |
| `export.error_policy` / `auto_export.error_policy` | db | strict/best-effort/partial/required-core | What happens when an export fails. Defaults: strict for manual, best-effort for auto. (doc) | `strict` / `strict` | No silent partial exports. |
| `import.auto` | yaml | bool | Legacy: imports JSONL after merge/checkout. Skipped once `sync.remote` is set. (src) | `false` | JSONL import is upsert-only and can bring back stale beads. |
| `import.orphan_handling` | db | allow/skip/resurrect/strict | Children whose parent is missing, on import or `bd dolt pull`. (doc) | `strict` | No orphans. Not tested. |
| `status.custom` | db (yaml fallback) | `name[:active\|wip\|done\|frozen],…` | Adds statuses. Unknown statuses are rejected. (exp) | unset | The built-ins (open/in_progress/blocked/deferred/closed, plus pinned/hooked) already cover shelf's three not-ready states. |
| `types.custom`, `types.infra` | db (yaml fallback) | csv | Adds types. Unknown types are rejected. Built-in types cannot be removed. (exp) | unset | |
| `issue_id_mode` | db | hash/counter | ID scheme. (doc) | `hash` | Safe with several agents and branches; counter IDs diverge across branches. |
| `min_hash_length`, `max_hash_length`, `max_collision_prob` | db | int / int / float | Adaptive ID length. (doc) | default | |
| `issue_prefix` | db | string | Set by `bd init --prefix`. | the repo name | |
| `no-hooks` | yaml/env | bool | Turns off `.beads/hooks/on_create\|on_update\|on_close`. Those hooks run async and fire-and-forget, so they **cannot veto** a write. (src) | `false` | |
| `no-git-ops` | yaml | bool | Drops git commands from the `bd prime` close protocol and skips the export git-add. (src) | `true` | Under shelf's conservative profile agents don't commit or push unless asked. |
| `no-push`, `no-db`, `json` | yaml | bool | Skip push in `bd dolt push` / JSONL-only mode / JSON output by default. (doc) | `false` / `false` / unset | `json` is a per-agent preference. |
| `git.author`, `git.no-gpg-sign`, `events-export` | yaml | str/bool | **dead** in 1.1.2 (src). | unset | |
| `output.title-length` | yaml | int (0 = hide) | How much of the title mutating commands echo. (doc) | default | |
| `routing.mode/default/maintainer/contributor`, `beads.role` | yaml / git | auto/maintainer/contributor/explicit; `beads.role` lives in `.git/config` | Where new beads are written. Contributors go to `~/.beads-planning`. (doc) | `maintainer`, `.` | `beads.role` is per clone and cannot be committed, so the doctor has to check it. |
| `federation.remote/sovereignty/allowed-remote-patterns/exclude_types` | yaml | URL / T1–T4 / globs / types | Peer federation. (doc) | unset | `bd config validate` reports a missing `federation.remote` even when `sync.remote` is set. That is a false positive. |
| `directory.labels`, `external_projects`, `repos.*` | yaml | maps | Monorepo label scoping, cross-project deps, multi-repo hydration. (doc) | unset | |
| `compaction_enabled`, `auto_compact_enabled`, `compact_*` | db | bool / ints | AI summary of old closed issues (`bd admin compact`). (doc) | `false` | Lossy: it rewrites history content. Deleting beads is a separate decision from summarizing them. |
| `ai.model`, `ai.api_key` | yaml | model id | Only used by `bd find-duplicates --method ai`. (src) | default | |
| `metrics.disabled/endpoint/notice_shown` | **user** | bool/url | Anonymous telemetry. Already `disabled: true` at user level. | do not touch | User-scoped. |
| `doctor.suppress.<slug>` | db | bool | Hides doctor warnings. **`bd doctor` is unsupported in embedded mode** (it prints a note and exits 0). (exp) | unset | Moot here. |
| `jira.* linear.* github.* gitlab.* ado.* notion.* custom.*` | db (tokens: yaml/env) | | Tracker integrations. | unset | |
| `dolt_mode`, `dolt_database`, `project_id` | meta | | Written by `bd init`. | leave | |

Blueprint snippet (nested YAML only; `bd config set` can also write flat dotted keys such as `validation.on-create: "error"` next to nested ones):

```yaml
validation: {on-create: error, on-close: error, on-sync: error,
             metadata: {mode: error, fields: {branch: {type: string}, commit: {type: string}}}}
create: {require-description: true}
hierarchy: {max-depth: 2}
dolt: {auto-commit: "on", auto-push: false}
backup: {enabled: false}
export: {auto: false, git-add: false}
import: {auto: false}
no-git-ops: true
# db, via bd config set: issue_id_mode=hash, import.orphan_handling=strict, export.error_policy=strict, auto_export.error_policy=strict
```

## Gaps beads cannot enforce (what a custom doctor script has to check)

All of these were reproduced by experiment unless marked otherwise.
1. **Edits after create skip validation.** `bd update --acceptance "" -d ""` clears both fields. `bd update -t bug` changes the type without re-validating.
   Check: `bd lint --status all`. It exits 1 on any missing section; with no flag it checks only `open`.
2. **Claiming is ungated.** `bd update --claim` moves a bead with no AC to in_progress, and no key prevents it.
   Check: every `in_progress` bead passes lint and has an assignee.
3. **Closing through update skips `on-close`.** `bd update -s closed` leaves `close_reason` empty.
   Check: every closed bead has a close reason of 20+ characters. The check also needs a rule for "AC met" evidence, such as a commit in metadata.
4. **`hierarchy.max-depth` is not enforced.** Check: the ID depth (count of `.`) and the parent-child dependency depth.
5. **Escape hatches.**
   - Env vars: `BD_VALIDATION_ON_CREATE=none` (and every `BD_*`) override the yaml.
   - `.beads/config.local.yaml` overrides the yaml and is **not gitignored** by default.
   - `--dolt-auto-commit off` on the command line.
   Check: no `config.local.yaml` exists, and no `BD_VALIDATION*` vars are set in agent environments or hooks.
6. **Config drift.** Check: the effective `bd config show` matches the blueprint. Also check `beads.role=maintainer` (in `.git/config`) and that flat and nested yaml keys are not both present.
7. **Built-in types and statuses can't be restricted.** Check: no `story`/`milestone`/`pinned`/`hooked` beads (or whatever the policy allows).
8. **Shelf conventions** (from AGENTS.md):
   - Every `deferred` bead names a trigger in its defer reason.
   - `blocked` status has a comment.
   - `--spec-id` points to an existing file.
   - No synthetic blocker beads.
9. **Labels.** No key requires a label or limits labels to an allowlist. Check that labels belong to the allowed vocabulary.
10. **Metadata `required` is global, not per type.** Per-type required metadata needs the script.
11. **Issue hooks can't block** (they are async). Hard gates belong in git `pre-commit`/`pre-push`, which already run `bd hooks run`, or in CI.
12. **Not available in embedded mode:** `bd doctor`, `bd sql`. Use `bd lint`, `bd list --json`, `bd show --json`, and `bd config show`.
13. **Side effects of `bd init`.** It auto-commits to git and writes `AGENTS.md`, `CLAUDE.md`, `.claude/settings.json`, `.codex/*`, `.agents/skills/beads/`, and git hooks (`core.hooksPath=.beads/hooks`). The blueprint has to reconcile these with the repo's own files.
