# Plugin tooling research: eval, details, tag, skill authoring, /skill-doctor

Sources (fetched 2026-10-10). Items marked UNSURE were not confirmed in the docs.

- Plugin eval: https://code.claude.com/docs/en/plugin-evals.md
- CLI reference (validate, tag, details, eval): https://code.claude.com/docs/en/plugins/cli-reference.md
- Plugin manifest: https://code.claude.com/docs/en/plugins/manifest-reference.md
- Cost and usage: https://code.claude.com/docs/en/plugins/measure.md
- Skills: https://code.claude.com/docs/en/skills.md
- Skill authoring best practices: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices

## 1. `claude plugin eval`

Docs require Claude Code v2.1.269+. Generally available. Local check: the installed build here reports `2.1.259 (Claude Code)` and already lists `plugin eval` in `--help`, so the docs version floor and this build disagree. Run `claude update` before relying on the documented behaviour.

### Layout (in the plugin root)

```
<plugin>/
├── .claude-plugin/plugin.json
├── skills/...
└── evals/                      # default; or "experimental": {"evals": "qa/evals"} in plugin.json
    ├── <case>/
    │   ├── prompt.md           # frontmatter = case fields; body = the user prompt
    │   ├── case.yaml           # optional; only for context.* and execution.prompt
    │   ├── graders/<name>.md   # one grader per file; frontmatter = type + options; body = rubric/pattern
    │   ├── mocks/              # optional per-case MCP mocks
    │   └── <fixtures referenced by case.yaml>
    ├── mocks/                  # optional suite-wide MCP mocks
    └── results/<timestamp>/    # written per run; gitignore it
        ├── aggregate-result.json
        └── report.html
```

A directory is a case if it holds `prompt.md` or `case.yaml`. A case with no grader fails to load (`invalid case.yaml`, names `graders`).

### prompt.md frontmatter (defaults)

| Key | Default | Notes |
|---|---|---|
| `schema_version` | `"1.1"` | Set automatically |
| `name` | directory name | `--case` globs match it |
| `description` | | human only |
| `tags` | `[]` | `--tag` filter |
| `plugins` | nearest enclosing plugin | e.g. `["../.."]` when auto-detection misses |
| `runs` | 3 | 1 to 50 |
| `expected_outcome` | | human only |
| `model` | child session default | `--model` overrides |
| `max_turns` | 10 | up to 200; hitting it is a run error |
| `timeout_seconds` | 300 | up to 3600 |
| `allowed_tools` | [] | read-only tools only, unless granted via `--allow-tools` |
| `append_system_prompt` | | |
| `env` | {} | keys must match `EVAL_[A-Z0-9_]*` |

Unknown frontmatter keys are an error.

### case.yaml (context and fixtures)

- `context.scaffold_script`: Bash script in the case dir, run in the empty workspace before Claude starts. Runs only with `--scaffold`, minimal env, 120 s limit, non-zero exit fails the run. It runs as you, outside the agent sandbox.
- `context.history_file`: `.jsonl` transcript to resume; the case prompt becomes the next turn.
- `context.add_dirs`: directories inside the case dir Claude may read, read-only (example in docs: `add_dirs: [resources]`).
- `execution.prompt`: prompt inline when `prompt.md` is omitted.
- `graders`: list of graders, same keys as the grader files.

There is no declared fixture or repo directory. Each run starts in an empty throwaway workspace.

- `scaffold_script` (Bash, in the case dir) runs in that empty workspace, only with `--scaffold`. Its environment is minimal: shell `PATH`, a temporary `HOME`, `TMPDIR`, and constants such as `TERM=dumb`. `EVAL_*` variables do not reach it. Limit: 120 s; non-zero exit or timeout scores the run 0 with `scaffold failed`. It can supply files and git state only; project config it writes is not loaded.
- `add_dirs` grants read access to case-dir directories, not writes.
- Writes by the agent need `--allow-tools Write Edit` (or `Bash`) at run time.
- UNSURE whether a scaffold can copy a whole repo from outside the case dir. The docs say the script lives in the case dir; the practical route is to commit the fixture repo into the case dir and copy it in the script.

### Grader frontmatter

Common keys: `type` (required), `weight` (default 1), `arm` (`with-only` or `both`). Under the two-arm mode, `with-only` graders (including `tool_used: Skill`) are a plugin-fired indicator, not part of the score.

What a grader can read (`target` for regex, and so on):
- `last_message` (default): final reply text.
- `trace`: session as JSON, one message per line.
- `files`: paths created during the run (not contents; not scaffold files; not modified files).
- `{source: file, path: <path>}`: contents of one workspace file after the run. Use this to grade what the skill wrote.
- `mock_calls`: calls to mocked MCP tools.

Types:

| Type | Options | Passes when |
|---|---|---|
| `regex` | `pattern`, `flags` (e.g. `i`), `match` (`contains` default, `not_contains`, `count:N`), `target` | JS regex found; `(?i)` not supported, use `flags: i` |
| `tool_used` | `tool`, `input_match`, `min` (default 1), `max` | call count within bounds; "never call" = `min: 0, max: 0` |
| `tool_order` | `before`, `after` | both called, first `before` precedes first `after` |
| `file_exists` | `path` (glob), `exists` (default true) | a created file matches |
| `llm` | `criteria`, `focus` | judge votes PASS in at least 2 of 3 |
| `baseline` | `baseline_file` (.jsonl in case dir), `criteria` | judge rates run at least as good as reference transcript |

`regex`, `tool_used`, `tool_order`, `file_exists` cost nothing (no judge). `llm` and `baseline` add judge calls. Skill-trigger check idiom: `type: tool_used`, `tool: Skill`, `input_match` against the skill name.

Minimal grader example (`graders/fixes-applied.md`):

```markdown
---
type: file_exists
path: "*.patch"
---
```

(A deterministic check of the repo state is better served by `{source: file}` plus `regex`, or by an `llm` grader on the diff file.)

### Baseline arm

By default a case runs with the plugin and without it (`--ablation with-without`). Output: `WITH`, `W/OUT`, `Δ`. Decided per case. `--ablation none` runs one arm only. Naming an installed plugin as target turns the baseline on. Graders marked `arm: with-only` are excluded from scoring in the two-arm mode.

### Mocks

`mocks/<server>/<tool>.md`: body is the canned result, with `{{input.x}}` and `{{file:fixtures/...}}` substitutions. Frontmatter `expect:` aborts the run (score 0) on an input violation. `type: agent` plays a server with a small model. Real MCP servers do not start under `--mocks record` (default).

### Commands

```bash
claude plugin eval init [name] [--bare] [-i|--interactive] [--eval-dir <dir>]
claude plugin eval [target] [options]
```

Target: plugin dir (default `.`), a single `prompt.md`/`case.yaml`, `name`, `name@marketplace`, or `name@skills-dir`. Put the target first; options like `--tag`, `--allow-tools`, `--json` swallow the following words.

Options (defaults):
- `--runs <n>` (case `runs`, else 3)
- `-j, --concurrency <n>` (1; 1 to 8)
- `--model <m>` (case `model`, else `ANTHROPIC_MODEL`, else default). Pin in CI.
- `--judge-model <m>` (help text says default `haiku`; docs call it the background-task model)
- `--ablation none|with-without`
- `--threshold <0..1>` (1.0)
- `--max-cost-usd <usd>` (no limit)
- `--allow-tools <tools...>`: grants `Bash`, `Write`, `Edit`, `WebFetch`, `WebSearch`, `mcp__...`. Example: `--allow-tools Write Edit "Bash(npm test *)"`.
- `--scaffold` (off), `--no-scaffold`
- `--trust-plugin` (off)
- `--mocks record|off` (record), `--allow-real-servers`
- `--json [path.json]`: quiet run; prints result document
- `--output-dir <dir>`, `--report <path>`, `--no-publish`, `--publish-report`
- `--case <glob>`, `--tag <t...>`, `--eval-dir <dir>`, `--keep-temp`, `--verbose`

Read-only tools granted by default in a run: `Read`, `Glob`, `Grep`, `NotebookRead`, `Skill`, `AskUserQuestion`, `Agent`, `TodoWrite`, `Task*`. A case's `allowed_tools` lists which of these it wants. Any other built-in tool is removed from the session unless granted with `--allow-tools`, which accepts `Tool(pattern:*)` syntax (e.g. `"Bash(npm test *)"`). A case's `allowed_tools` and a skill's `allowed-tools` cannot widen grants.

Exit codes: 0 all cases >= threshold; 1 below threshold, load error, no cases, run could not start, untrusted dir without `--trust-plugin`, bad option; 2 partial (cost ceiling or credential rejected); 130 interrupted; 143 terminated.

### JSON result

`--json` and `aggregate-result.json` share one document, `schemaVersion: 1`, camelCase, additive-only. Documented top-level and case fields: `partial`, `partialReason` (`cost_ceiling`, `interrupted`, `auth_failed`), `aggregates.overallScore`, `aggregates.casesPassed`, `aggregates.casesTotal`, `aggregates.meanDelta`, `cases[].name`, `cases[].aggregates.score`, `cases[].aggregates.delta`, `cases[].arms.with[].error`, `cases[].arms.with[].aborted`, `cases[].arms.with[].skippedPaidGraders`, `costUsd`, `durationSeconds`, `claudeVersion`. UNSURE: the full per-grader field names under `arms.with[].graders[]`; fetch the page and check the JSON result section, or run once with `--json` and inspect.

### CI

Docs example:

```bash
claude plugin eval . \
  --trust-plugin \
  --json results.json \
  --threshold 0.8 \
  --model claude-sonnet-5 \
  --judge-model claude-haiku-4-5 \
  --no-publish \
  --max-cost-usd 20
```

Needs a Claude Code install and credentials in env (`ANTHROPIC_API_KEY` or the cloud provider variables). `claude plugin eval init` needs a TTY; in CI use `init --bare <name>`. The delta never changes the exit code.

### Sandbox

- Per run: a `claude -p` child with a temporary home, working dir, and config dir. Only the plugin under test loads. Absent: user settings, user and project hooks, every `CLAUDE.md`, `.mcp.json`, other plugins, memory, and skills outside the plugin. `.claude/` directories are not read, even ones a scaffold writes.
- Most of the shell environment is withheld. Only an allowlist (PATH, locale, proxy and certificate settings, provider selectors and credentials, most `ANTHROPIC_*`/`CLAUDE_CODE_*`) and `EVAL_*` pass through. Ship any skill, agent, hook, or MCP server a case depends on inside the plugin.
- The eval directory is hidden from the agent: it cannot read the case prompt, graders, or sibling cases.
- Managed settings on the machine still apply inside runs.
- Granting `Bash` runs commands under Claude Code's OS-level sandbox (writes confined to the workspace; network limited to `--allow-tools "WebFetch(domain:...)"` grants). On a machine with no sandbox backend, runs are refused rather than run unconfined. Linux needs `bubblewrap` and `socat`. Native Windows needs WSL2.
- Not a security boundary for the plugin's own code: hooks, scaffold scripts, and real MCP servers run outside the agent sandbox as you. Only evaluate trusted plugins.
- Artifact tool is off in runs. No network sandbox outside shell commands: a `WebFetch(domain:...)` grant reaches that domain directly, and plugin hooks or real MCP servers can reach any host.
- Trust prompt: first run in an untrusted dir asks `Trust this plugin directory? [y/N]`. Refused without a TTY or under `--json`; pass `--trust-plugin` in CI. Installed `name@marketplace` targets skip the prompt.

### Cost

- Roughly cases × runs agent runs with the plugin, the same again for the baseline, plus 3 short judge calls per `llm`/`baseline` grader per run.
- Reported `costUsd` is a list-price estimate, not plan usage. Docs sample: one case, 6 runs, $0.41.
- Cap with `--max-cost-usd`. Quick every-change suites: use non-judge graders and `--ablation none`.

### Availability

Generally available. The embedded reference says a server-side kill switch can make it print `` `plugin eval` is currently unavailable `` and exit 1. "early access" message means an old build: run `claude update`.

## 2. `claude plugin details`

Syntax:

```bash
claude plugin details <name>
claude --plugin-dir ./ plugin details <name>   # for an unloaded plugin in the cwd
```

`<name>` is `name` or `name@marketplace`. The plugin must be loaded: installed, in a skills directory, or passed with `--plugin-dir`/`--plugin-url` in the same command. No flags beyond `--help`. Not found: prints a message and exits 1.

What it reports (from docs example; UNSURE that exact spacing matches your build):

```
formatter 1.0.0
  Description: Formats and lints code on save
  Source: formatter@my-marketplace

Component inventory
  Skills (3)  format-all, format-code, lint-fix
  Agents (1)  style-reviewer
  Hooks (1)  PostToolUse  (harness-only — no model context cost)
  MCP servers (1)  formatter-tools  (tool schemas resolved at runtime; not counted)
  LSP servers (0)

Projected token cost
  Always-on:   ~146 tok   added to every session

Per-component (rounded)
  component       always-on  on-invoke
  format-code           ~40        ~30
  ...
  On-invoke cost is paid each time a skill or agent fires.
  Token counts are estimates and may differ from actual usage.
```

Meanings:
- Always-on: name + `description` + `when_to_use` of every skill, agent, and command. Paid every session the plugin is enabled.
- On-invoke: the body that loads when the component runs.
- Commands count as skills. Hooks and MCP servers get no token estimate; check MCP tool cost with `/context` (`MCP tools` row).
- Docs: plugins in the official marketplace show a "Context cost" section; own marketplace plugins do not.

## 3. `claude plugin tag`

Syntax:

```bash
claude plugin tag [path] [--push] [--dry-run] [-f|--force] [-m|--message <msg>] [--remote <name>]
```

- Creates an annotated tag `<name>--v<version>` (double hyphen before `v`). Example: `formatter--v1.0.0`.
- Default path `.`. Finds the marketplace entry by walking up from the path to a `.claude-plugin/marketplace.json` that lists the plugin.
- Message default `<name> <version>`; `%s` = version.
- `--push` pushes to `--remote` (default `origin`). If push fails, the tag stays local and exit is nonzero.
- `--dry-run`: prints plugin name, version source file, matching marketplace entry, tag name, and the git commands. Example: `claude plugin tag plugins/formatter --dry-run`.
- `-f/--force` skips dirty-tree and tag-exists checks.

Validation it does:
1. Version must exist in `plugin.json` or the marketplace entry, and the two must agree. This is the one check the docs describe explicitly.
2. Refuses a name that the validator flags as reserved (starts with `claude-`, `anthropic-`, `anthropics-`, `cc-plugin-`; or is `claude`, `anthropic`, `anthropics`, `claude-code`, `claude-mods`; etc.). Name must be kebab-case, no spaces, `@`, `:`, or path separators.
3. Refuses if the tag already exists or the working tree is dirty (unless `--force`).

UNSURE: whether `tag` runs the full `claude plugin validate` checks. The docs do not say so. Run `claude plugin validate . --strict` before tagging.

Version is not checked against semver. Note: `"version"` in `plugin.json` pins users to that version until changed. Your marketplace uses `source: "./"`, so the plugin root is the repo itself, and the tag is found by walking up to the root `marketplace.json`.

## 4. Skill authoring constraints

### SKILL.md frontmatter (Claude Code)

Location: `skills/<name>/SKILL.md`. The opening `---` must be line 1. Every field is optional; `description` is recommended. Unknown keys are ignored in Claude Code. Malformed YAML: the skill loads with empty metadata.

| Field | Notes |
|---|---|
| `name` | Defaults to dir name. Reserved: `synced`, `anthropic-skills`, and anything starting `anthropic-skills:`. |
| `description` | Recommended. Defaults to first non-empty body line. |
| `when_to_use` | Appended to description; counts toward the cap. |
| `argument-hint` | Autocomplete hint. |
| `arguments` | Named args for `$name` substitution. |
| `disable-model-invocation` | default false; true stops auto-loading and subagent preload; as of v2.1.196 also stops scheduled runs. |
| `user-invocable` | default true. |
| `allowed-tools` | Tools usable without prompt during the invoking turn. Space/comma list or YAML list. Grant clears on next user message. |
| `disallowed-tools` | Removed from pool while active. |
| `model` | `/model` values or `inherit`. |
| `effort` | `low`, `medium`, `high`, `xhigh`, `max`. |
| `context` | `fork` runs in a subagent. |
| `agent` | subagent type when `context: fork`. |
| `background` | only with fork; default true; needs v2.1.218+. |
| `hooks` | Skill-scoped hooks, see below. |
| `paths` | glob limiting auto-activation. |
| `shell` | `bash` (default) or `powershell` for `` !`cmd` `` blocks. |
| `metadata` | free-form map; ignored by Claude Code. |
| `license`, `compatibility` | accepted, not acted on. `compatibility` max 500 chars. |

Portability (claude.ai upload, Skills API, `package_skill.py`): only `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools` allowed. Any other key is a hard error (example: `Unexpected key(s) in SKILL.md frontmatter: argument-hint`). Since the user's skill is for the plugin marketplace, keep to the portable set if it may also ship elsewhere.

### Name and description limits

- `name`: Claude Code docs state no length limit. Platform docs (API/claude.ai rules): max 64 chars, lowercase letters, digits, hyphens; no XML tags; no `anthropic`/`claude` words. UNSURE which the Claude Code loader enforces; assume the 64-char platform rule.
- `description`: Claude Code truncates the combined `description` + `when_to_use` in the skill listing at 1,536 chars. Platform docs say max 1,024 chars and non-empty, no XML tags. Target at most 1,024 chars to satisfy both.
- Plugin manifest `name`: kebab-case, no spaces, `@`, `:`, path separators; must not look like an Anthropic plugin name (see tag section).

### Hooks in skills

Yes. Skill frontmatter `hooks:` registers hooks when the skill is invoked; they persist until the session ends. Plugins can also declare hooks at plugin level via `hooks/hooks.json` or the manifest `hooks` key (`.json` path or inline object). Plugin hook commands should use `${CLAUDE_PLUGIN_ROOT}`, quoted in shell form (or exec form with `args`). Hooks in plugins run outside the eval sandbox.

### How files load

- Only `name` and `description` (plus `when_to_use`) sit in context at all times.
- The full SKILL.md body loads when the skill is invoked. After compaction, the first 5,000 tokens of each invoked skill are kept; re-attached skills share a 25,000-token budget.
- Supporting files (`reference.md`, `examples.md`, `scripts/...`) are NOT auto-loaded. SKILL.md must reference them by relative link, and Claude reads them with its file tools when needed.
- Scripts are executed (their output enters context), not loaded.
- The docs' example layouts use `reference.md`, `examples.md`, `scripts/`. A `references/` folder is not named in the Claude Code docs. UNSURE whether it is special; it should work as a plain path referenced from SKILL.md.
- Keep references one level deep from SKILL.md. Add a table of contents to reference files longer than 100 lines.

### Sizes

- SKILL.md body: keep under 500 lines (Claude Code docs and platform docs agree). No hard cap found.
- Listing budget: skill descriptions share a listing budget of 1% of the context window; overflow drops descriptions starting with least-used skills. `/doctor` estimates it. Settings: `skillListingBudgetFraction`, env `SLASH_COMMAND_TOOL_CHAR_BUDGET`, `skillListingMaxDescChars`.
- Plugin validation of skills: `claude plugin validate .` validates manifest and component files, including `skills/`. `claude plugin validate skills` validates the directory directly. Frontmatter parse errors surface there.

## 5. `/skill-doctor`

- Generally available. Only suggest if it appears in the build's command list (`/skill-doctor` is listed in this session).
- No arguments. Interactive: opens the plugin manager's Stats tab (same as `/plugin stats`). `-p`, Remote Control, and background sessions: prints text.
- Reports per-skill listing cost, 7-day tokens and uses, skills in the listing that were never invoked (including plugin skills), and unused plugins.
- Not a linter. Use `claude plugin validate` for structure and `claude plugin eval` for behavior.
- Docs: https://code.claude.com/docs/en/plugins/measure.md (section "Find skills that never run"). The skills page cross-links it as "Find unused skills".

## Manifest requirement for this repo

Eval needs a plugin directory with `.claude-plugin/plugin.json`, or a skills-directory plugin. A repo with only `.claude-plugin/marketplace.json` and `source: "./"` is not enough. `claude plugin validate .` on a directory with both marketplace.json and plugin.json validates both (v2.1.289+).

If auto-detection misses the plugin from a case, set `plugins: ["../.."]` in `prompt.md`.

`details` needs the plugin loaded. For an uninstalled local plugin, run `claude --plugin-dir <absolute-root> plugin details <name>`. `<name>` is the `name` in `plugin.json`, not the marketplace entry name if they differ.

## Open questions for your build

1. Update Claude Code. Docs require v2.1.269+ for `plugin eval`; the local build here is 2.1.259 and still has the command. Help output was checked locally for `eval`, `tag`, and `details` (flags listed in the sections above match `--help`, except `--judge-model` default and `--allow-tools` pattern syntax, which were taken from the help text).
2. Confirm whether `claude plugin tag` runs the same checks as `validate`. Run `validate --strict` first.
3. Confirm the `aggregate-result.json` grader field names before writing any parser. The docs say the document includes suite config, every grader definition, and per-run grader results with explanations and evidence, but the nested key names were not retrieved.
4. Decide whether a scaffold script can copy a repo fixture from outside the case directory (not documented).
