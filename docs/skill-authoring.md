# Skill authoring — how to build a skill that works, stays cheap, and keeps improving

The reference for writing any agent skill: a `Kind: skill` member under `skills/<name>/`
(resolution 0014), a shelf-internal one under `.agents/skills/`, or a skill in any other repo.
`docs/linting.md` is the reference for code; this file is the reference for skills.

> **Status: one research pass, 2026-10-10, not cross-checked.** Collected while designing
> `blueprint` (`openspec/changes/blueprint-skill/`). Every claim names its source; the raw research
> with full tables is in that change's `research/skill-practices.md` and `research/plugin-tooling.md`.
> Two sources were read secondhand (marked). A claim marked *untested* has not been run here.
> Claude Code version at the time: 2.1.296.

**Sources** (keys used below):

| key | source |
|---|---|
| BP | platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices |
| OV | platform.claude.com/docs/en/agents-and-tools/agent-skills/overview |
| CC | code.claude.com/docs/en/skills |
| PE | code.claude.com/docs/en/plugin-evals |
| PR | code.claude.com/docs/en/plugins-reference, …/plugins/cli-reference, …/plugins/manifest-reference, …/plugins/measure |
| AS | agentskills.io — specification; skill-creation best-practices, using-scripts, evaluating-skills, optimizing-descriptions |
| BLOG | anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills |
| SC | Anthropic's `skill-creator` plugin skill |
| SP | github.com/obra/superpowers — `writing-skills`, `docs/testing.md`, positive-instruction redesign spec (2026-06-10); read through a fetched summary |
| TH | Thariq, "Lessons from Building Claude Code: How We Use Skills", 2026-03-17; read through a mirror |
| MP | Matt Pocock's skills plugin — `writing-for-agents` (SKILL.md, SKILL-MECHANICS.md), CLAUDE.md, CHANGELOG.md |
| ML | the owner's `my-language` skill — SKILL.md, evidence.md, calibration.md, mine.py, workspace check.py, Stop hook |
| PA | the owner's earlier `agent-harness` and `agent-weiss` (`blueprint-skill/research/prior-art.md`) |
| M | measured on this machine with `claude plugin details` / `validate` |

---

## 1. How a skill costs tokens

| level | what loads | when | cost |
|---|---|---|---|
| 1 | `name` + `description` (+ `when_to_use`) | every session the skill is installed, model-invoked or not disabled | ~100 tok per skill, paid always (OV) |
| 2 | the SKILL.md body | when invoked | aim < 5k tok (OV) |
| 3 | referenced files | only when the agent reads them | 0 until read |
| — | scripts | executed; only their output enters context | output only (OV, AS) |

Facts that shape everything else:

- **The listing budget is 1% of the context window.** On overflow Claude Code drops the
  descriptions of the *least-invoked* skills first (CC). A rarely used skill is the first to go
  invisible.
- **SKILL.md is read once.** Later turns do not re-read it, so write standing rules ("for every
  checkpoint…"), not one-time steps (CC).
- **After compaction each invoked skill keeps its first 5,000 tokens;** all re-attached skills
  share 25,000 (CC). The rules that must survive go in the first screen.
- **Measured always-on cost (M, 2026-10-10):** skill-creator ~110 tok; the owner's k-my plugin,
  23 skills, **~4,326 tok every session**; one 2,000-character description (my-language) ~700 tok.
  Measure yours: `claude plugin details <name>` (an unloaded local plugin:
  `claude --plugin-dir <abs-root> plugin details <name>`). `/skill-doctor` lists skills never
  invoked in 7 days.

## 2. Layout and size

- **SKILL.md under 500 lines** (BP, CC, AS, SC). A cost argument, not a behaviour cliff: ML's
  calibration recorded "289 lines was too long" as a wrong prediction.
- **References one level deep.** Nested chains get partial reads (`head -100`) (BP, AS).
- **A table of contents on any reference file over 100 lines** (BP; SC says 300 — use 100).
- **Say when to load each file:** "read `stacks/dotnet.md` if the repo has a `.csproj`", never
  "see references/" (AS).
- **Split by domain:** one reference file per area or variant (`aws.md`, `gcp.md`); the agent reads
  only the one in play (BP pattern 2, SC). Overly complete skills hurt: the agent follows
  instructions that do not apply (AS).
- **Authoring unit ≠ loading unit.** When a skill has many items (a 100-item checklist), author one
  file per item (constitution I–II: conflict-free parallel work, per-item expiry) and *generate*
  one reference file per area plus an index in SKILL.md. Never hand-write an index that restates
  frontmatter: the k-my `INDEX.md` already drifts from its skills' descriptions (MP router pattern;
  observed).
- **Evidence stays outside the load path.** ML keeps 1,082 lines of measurements in `evidence.md`,
  which SKILL.md cites but never loads.
- **Gotchas live in the SKILL.md body, short** — the highest-value content, and the agent may not
  know when to open a file holding them (AS, TH).
- **Point at the environment, don't copy it.** Restating a tool's config or `--help` is a stale
  cache (MP "pruning").
- **Name = directory name.** The open standard requires it (AS); nothing in the toolchain checks
  it — `fable-council/SKILL.md` says `name: my-fable-council` and `claude plugin details` accepts it
  (M). Enforce with a test.

## 3. Frontmatter

| field | use |
|---|---|
| `name` | ≤ 64 chars, lowercase, digits, hyphens; no `anthropic`/`claude` (platform rule; Claude Code's own limit undocumented) |
| `description` | **≤ 1,024 chars** (open standard). Claude Code truncates description + `when_to_use` at 1,536 in the listing (CC). `claude plugin validate` passed a 1,620-char description (M), so enforce 1,024 with a test |
| `disable-model-invocation: true` | the skill leaves the listing: zero always-on cost, invoked only as `/name` (CC) |
| `allowed-tools` | pre-approves tools for the invoking turn only |
| `hooks` | skill-scoped hooks, live from invocation to session end |
| `context: fork` + `agent` | run in a subagent without the conversation |
| `paths` | globs limiting auto-activation |

**Portable set:** claude.ai upload, the Skills API and `package_skill.py` accept only `name`,
`description`, `license`, `compatibility`, `metadata`, `allowed-tools`; any other key is a hard
error there (PR). Claude Code ignores unknown keys.

## 4. Triggering

- **Model-invoke only if the agent must reach the skill unprompted** (or another skill must). A
  skill started on purpose — a kickoff, an audit, a release — is better user-invoked
  (`disable-model-invocation: true`) and pointed to from the repo's AGENTS.md (MP; cost data in §1).
- **A description is what + when, never the workflow.** Agents followed a description's summary of
  the steps and skipped the body's second review step (SP, TH).
- **"Use when…", triggers only, front-load the leading word, one trigger per branch** — synonyms
  of one branch are waste (AS, MP).
- **One-step tasks do not trigger skills** whatever the description; only work the agent cannot
  easily do alone (SC, AS). A prompt that needs no tool at all is reachable only by always-loaded
  text — CLAUDE.md / AGENTS.md (ML).
- **Trigger evals:** ~20 queries, 8–10 should-trigger, 8–10 *near-miss* should-not; 3 runs each;
  pass at rate 0.5; 60/40 train/validation; pick by validation; ~5 iterations (AS, SC). Don't
  overfit to the failed queries' keywords (AS).
- ⚠️ **skill-creator's `run_eval.py` scored 0 triggers in 40 runs**, positives included — it tests a
  temporary slash command, which is never auto-invoked. "A harness that cannot detect a true
  positive reports nothing, and its result is void" (ML calibration). Use `claude plugin eval`
  with a `tool_used: Skill` grader instead (PE).

## 5. Writing instructions

| finding | source |
|---|---|
| Explain *why*; ALL-CAPS MUST is a yellow flag | SC, AS |
| **Shape output with a positive recipe, not a prohibition.** "Don't restate the brief" scored 4.4 re-typed values — worse than no guidance (3.6); a positive recipe scored 3.0 with zero variance; adding a nuance clause pushed it to 3.8 and noisy (opus, 5 reps) | SP |
| Prohibitions that do work: tripwires on concrete tokens, red-flag tables, discrete policy gates ("do not commit") | SP |
| Match the form to the failure: skipped under pressure → red-flag table; wrong shape → recipe; missing element → required template field | SP |
| Defaults, not menus: one tool per job with an escape hatch | BP, AS |
| One term per concept, everywhere | BP |
| Existing words over coinages; a repeated pretrained word anchors behaviour cheaply | MP |
| Add only what the model lacks: "would the agent get this wrong without this?" | BP, AS |
| Railroading hurts where goals would do (TH); checklists are right for fragile multi-step flows (BP) — use each where it fits | TH, BP |

## 6. Scripts

- **Three kinds of code, three rules.** Scripts that handle the skill's own structure —
  enumerate its items, validate its output format, project its sources into references — exist
  from day one: they are what stops an agent faking a result (Fable A, `blueprint-skill` design
  D8). The judgment the skill teaches is never scripted. Every other helper is extracted when eval
  transcripts show every run re-writing it — not before (SC, AS, BLOG). Fragile or
  sequence-critical steps become code (BP "degrees of freedom").
- **Never wrap tools.** agent-harness wrapped ruff, biome and others in its own CLI and broke when
  their flags changed (PA). Run the tool as itself, from the repo's own task runner.
- **Script contract for agents** (AS): non-interactive; `--help`; JSON or CSV to stdout,
  diagnostics to stderr; distinct documented exit codes; idempotent; `--dry-run`; bounded output
  (harnesses truncate around 10–30k chars). Say whether a script is to be *run* or *read* (BP).
- **Plan → validate → execute** for changes: write a plan file, validate it with a script, apply
  (BP, AS).
- **A check proves the effect, never the artifact** — the onboard-consumer operations assert by
  exercising (`Result.verified`); agent-weiss's file-existence checks inverted its own scores (PA).
- **Injected commands (`` !`cmd` ``) run before the skill renders; any non-zero exit aborts the
  invocation** — append `|| true` to anything that exits 1 on findings (CC).
- Reach bundled files with `${CLAUDE_SKILL_DIR}`. No plugin `bin/`: claude.ai and Cowork refuse to
  install a plugin with one (PR).
- **In the shelf:** script logic goes under `tools/` with tests under `tests/`, and the skill holds
  a thin caller (the onboard-consumer precedent). Today pyrefly and coverage cover `packages/` only,
  so `tools/` is outside the type gate too until shelf-yz4 extends it.

## 7. Evals — `claude plugin eval`

Layout (PE):

```
<plugin>/evals/<case>/
  prompt.md            # frontmatter: name, tags, runs (3), max_turns (10), timeout_seconds (300),
                       # allowed_tools, model, env (EVAL_* only); body = the user prompt
  case.yaml            # optional: context.scaffold_script, context.history_file, context.add_dirs
  graders/<name>.md    # one per file; a case with no grader fails to load
```

- **Every run starts in an empty workspace.** A fixture repo is a `scaffold_script` (bash, in the
  case dir, runs only with `--scaffold`, 120 s, files and git state only; config it writes is not
  loaded). Commit the fixture into the case dir and copy it in.
- **Graders:** `regex`, `tool_used`, `tool_order`, `file_exists` (free); `llm` (2-of-3 judge votes)
  and `baseline` (vs a reference transcript) cost judge calls. **No custom-code graders.** Targets:
  `last_message`, `trace`, `files`, `{source: file, path: …}`, `mock_calls`.
- **So make the skill write a machine-gradable file** — one line per item, words from a closed set —
  and grade it with `regex`. `llm` graders drift on long text (PE).
- **Two arms by default**, with and without the plugin; Δ is the only number that says the skill
  helped. `tool_used: Skill` graders are reported, not scored (PE).
- **Seed cases only from observed failures, never predicted ones.** ML's calibration found every
  predicted failure wrong; "once a number exists it gets optimised against".
- **Pair every fault-finding case with a clean case,** or an agent that flags everything scores
  perfectly (ML's fact-retention companion rule).
- **Add assertions after the first outputs;** drop ones that pass in both arms, fix ones failing in
  both; PASS needs quoted evidence (AS).
- **Pressure scenarios** for discipline rules (the agent marking ✅ without proof); a RED baseline
  before writing the rule (SP).
- **Keep evals out of `make check`.** Live runs take minutes and cost money; run them on demand and
  before a tag (SP `tests/` vs `evals/` split). The gate keeps the static checks: frontmatter,
  description length, name = directory, generated files fresh.
- **CI form:** `claude plugin eval . --trust-plugin --json results.json --threshold 0.8
  --model <pinned> --judge-model <pinned> --no-publish --max-cost-usd 20` — exit 0 pass, 1 below
  threshold or load error, 2 partial. Docs example cost: one case × 6 runs ≈ $0.41.
- **Sandbox:** temp HOME and config; no user or project settings, CLAUDE.md, hooks, `.mcp.json`,
  memory or other plugins; env allowlisted; eval dir hidden from the agent. Not a security boundary:
  hooks and scaffolds run as you. Writes need `--allow-tools Write Edit` or `Bash`.
- **One eval format per skill.** skill-creator's `evals/evals.json` and plugin-eval case dirs both
  default to `evals/` and neither reads the other's files (PE) — use plugin eval.
- Needs Claude Code ≥ 2.1.269.

## 8. State across sessions

- An audit or build that spans sessions cannot live in the agent's context: SKILL.md is not re-read
  and compaction trims it (CC).
- **State about the target repo lives in that repo** (its tracker, a report file), never in the
  skill dir (replaced on update) (PR, TH). State about the user lives in `${CLAUDE_PLUGIN_DATA}`,
  kept across updates (PR).
- **A resume rule in the first screen:** after compaction, re-invoke the skill and re-read state
  from the repo (CC).
- A copyable progress checklist works within one session, not across sessions (BP, AS).

## 9. How a skill keeps improving

| practice | source |
|---|---|
| Every correction becomes a gotcha in the body, or a regression row `failure · rule · check` plus an eval case | AS, TH, ML calibration R1–R10 |
| Watch a second agent use the skill: file-read order, missed links, ignored files (Claude A writes, Claude B uses) | BP |
| A mining script re-derives the evidence from real transcripts; it also catches drift in the rule's own source | ML mine.py |
| A hook that **logs, never blocks**: a blocking gate fired on 28% of 4,959 turns | ML Stop hook |
| CHANGELOG with the *why* per change | MP |
| An expired rule moves to an "old patterns" block, then is deleted at RECONCILE | BP |
| Re-audit every skill on a new model release; delete instructions the model now follows unprompted | TH (secondhand) |
| Lifecycle: candidate → active → deprecated; only active ones ship as defaults | MP, shelf constitution V, VIII |
| Pruning pass: delete sentences that change nothing vs the model's default | MP |
| Every page or item says how you know it works ("it's working if…") | MP |

## 10. In the shelf specifically

- **Two tiers** (resolution 0014): `skills/<name>/` is `Kind: skill` — catalogued, plugin-distributed,
  evals required before `active`, measured always-on cost recorded in the catalog entry;
  `.agents/skills/` is shelf-internal, invoked by path, ungoverned.
- **Eval location — untested:** the shelf plugin's root is the repo (`source: "./"`), so the
  default suite is `shelf/evals/`, shared by every skill. To keep a skill's cases in
  `skills/<name>/evals/`, set `experimental.evals` on the marketplace entry or pass `--eval-dir`.
- **Tag format — untested:** `claude plugin tag` creates `<name>--v<version>`; the shelf rule is
  `<name>-vX.Y.Z`. Check with `--dry-run` before the first skill tag. Run
  `claude plugin validate . --strict` first; whether `tag` runs it is undocumented.
- **Fitness tests still to add** (none exists yet): description ≤ 1,024 chars; `name` equals the
  directory; generated references are fresh.

## 11. Anti-patterns

- Machinery before one working item: agent-weiss built state, reconcile, hashing, approval verbs and
  backups, and after four plans could not write a single file (PA).
- Spec, roadmap and distribution channels before the skill ran on one real repo (PA).
- Wrapping tool invocations (PA).
- One rule in three places (policy file + init code + skill prose) with no single source (PA).
- A contract no test enforces (PA: weiss's exit-code contract broken by 9 of 16 controls).
- Existence checks padding the count (README present, LICENSE present) (PA).
- Deep reference chains; time-sensitive text; magic constants; assuming tools are installed (BP).
- A workflow summary in the description (SP).
- A trigger harness that cannot detect a true positive (ML).
- An eval suite built from predicted failures (ML).
- A hand-maintained index restating frontmatter (observed in k-my).
