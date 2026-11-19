# Research: how to build a skill — practices for blueprint

> **One pass, not cross-checked.** Sources were read once, 2026-10-10. Two are secondhand:
> Thariq's "How we use skills" post was read through a mirror, not the original; superpowers'
> writing-skills was read through a fetched summary of its SKILL.md. Verdicts are the authoring
> agent's own (✅ take · ❌ leave · untested).

Source keys used below:

| key | source |
|---|---|
| BP | platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices |
| OV | platform.claude.com/docs/en/agents-and-tools/agent-skills/overview |
| CC | code.claude.com/docs/en/skills |
| PE | code.claude.com/docs/en/plugin-evals |
| PR | code.claude.com/docs/en/plugins-reference |
| AS | agentskills.io — /specification, /skill-creation/{best-practices,using-scripts,evaluating-skills,optimizing-descriptions} |
| BLOG | anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills |
| TH | Thariq, "Lessons from Building Claude Code: How We Use Skills", 2026-03-17, x.com/trq212/status/2033949937936085378 (via mirror gitea.maison43.duckdns.org/gilles/claude-code-best-practice/…/claude-thariq-tips-17-mar-26.md) |
| SC | `~/.claude/plugins/cache/claude-plugins-official/skill-creator/d182ca456ca0/skills/skill-creator/SKILL.md` |
| SP | github.com/obra/superpowers — `skills/writing-skills/SKILL.md`, `docs/testing.md`, `docs/superpowers/specs/2026-06-10-positive-instruction-redesign-design.md` |
| MP | `~/.claude/plugins/cache/claude-plugins-official/mattpocock-skills/1.2.3/` — `skills/productivity/writing-for-agents/{SKILL,SKILL-MECHANICS}.md`, `CLAUDE.md`, `CHANGELOG.md` |
| ML | `~/.claude/skills/k-my/skills/my-language/` — SKILL.md, evidence.md, calibration.md, mine.py; `my-language-workspace/{README.md,check.py}`; `k-my/hooks/` |
| K | `~/.claude/skills/k-my/` — INDEX.md, `code-to-spec-workspace/optimizer.log`, `micro-software/SKILL.md` |
| M | measured in this session: `claude plugin details`, `claude plugin validate`, `claude --version` |

## 1. Size and shape of SKILL.md

| claim | source | verdict for blueprint |
|---|---|---|
| Three load levels: metadata ~100 tok always; body <5k tok on trigger; files 0 until read; script code never enters context, only its output | OV table; AS spec | ✅ the cost model everything else rests on |
| Body under 500 lines; split when near it | BP, CC, AS, SC | ✅ hard ceiling for SKILL.md |
| References one level deep from SKILL.md; nested refs get partial reads (`head -100`) | BP "Avoid deeply nested references"; AS spec | ✅ — this decides the checkpoint layout (§3) |
| Reference files >100 lines get a table of contents at top (SC says >300) | BP; SC | ✅ use 100: per-area files will cross it |
| Tell the agent *when* to load each file ("read X if Y"), not "see references/" | AS best-practices | ✅ each area pointer names its trigger (stack detected, area in scope) |
| SKILL.md is read once; Claude Code does not re-read it on later turns; write rules as standing instructions | CC "Skill content lifecycle" | ✅ phrase the audit loop as "for every checkpoint…", not one-time steps |
| After compaction each invoked skill keeps its **first 5,000 tokens**; all re-attached skills share 25,000; most important instructions go at the top | CC lifecycle + troubleshooting | ✅ resume rule, verdict words and "not done" words go in the first screen |
| "Claude is already very smart" — add only what it lacks; each paragraph must justify its tokens | BP "Concise is key"; AS "Would the agent get this wrong without this?" | ✅ |
| Overly comprehensive skills hurt: agent follows instructions that don't apply | AS "Aim for moderate detail" | ✅ argues for loading only the areas in play |
| Sprawl, sediment, no-ops: delete whole sentences that don't change behaviour vs default | MP writing-for-agents "Pruning" | ✅ a pruning pass in RECONCILE |
| Environment is a source of truth; restating config/`--help` is a stale cache | MP "Pruning" | ✅ checkpoints point at the repo's own config, never copy it |
| Gerund names (`processing-pdfs`) preferred; noun/action acceptable | BP naming | ❌ `blueprint` is fine and already decided; not worth a rename |

Owner practice: my-language SKILL.md is 538 lines (over the 500 cap) plus a 1,082-line evidence.md
outside the load path (ML). Its own calibration.md records that "289 lines was too long" was a wrong
prediction (ML calibration.md). ⇒ the 500 cap is a cost argument, not a behaviour cliff.

## 2. Scripts vs instructions

| claim | source | verdict |
|---|---|---|
| Degrees of freedom: high (text) when many paths valid; low (exact script) when fragile or sequence-critical | BP | ✅ audit judgment = high; gate probes = low |
| Bundle a script when eval transcripts show every run re-writing the same helper | SC "Look for repeated work"; AS evaluating-skills; BLOG | ✅ confirms design principle 5 (no probes in v0.1) |
| Prefer scripts for deterministic ops; "solve, don't defer" error handling; no voodoo constants | BP "Advanced" | ✅ when probes arrive |
| Script interface for agents: non-interactive; `--help`; JSON/CSV to stdout, diagnostics to stderr; distinct documented exit codes; idempotent; `--dry-run`; bounded output (harnesses truncate ~10–30K chars) | AS using-scripts | ✅ the probe contract, verbatim |
| Pin tool versions in one-off commands (`uvx ruff@0.8.0`); PEP 723 inline deps + `uv run` for self-contained scripts | AS using-scripts | untested for shelf: principle 5 puts probe logic in `tools/` under the type gate instead |
| Plan-validate-execute: write a structured plan file, validate it with a script, then apply | BP; AS | ✅ fits "agent applies the fix": findings file → validate → apply |
| Say whether a script is to be *run* or *read* | BP | ✅ |
| `` !`cmd` `` injection runs before the skill renders; **any non-zero exit aborts the whole invocation** (exit 1 tolerated only for grep/diff-like commands); append `|| true` | CC "When an injected command fails" | ✅ if blueprint injects `git status`/stack detection; a check that exits 1 on findings must carry `|| true` |
| `${CLAUDE_SKILL_DIR}` resolves scripts at any install scope; `allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/x *)` pre-approves for one turn only | CC substitutions, allowed-tools | ✅ |
| Plugin `bin/` puts files on PATH, but claude.ai/Cowork refuse to install a plugin with `bin/` | PR standard layout | ❌ no `bin/` |
| Owner: check.py scores only what a script can judge "without argument"; judgment goes to the human, because "a script that pretended to check them would produce a green number that means nothing" | ML workspace README, check.py docstring | ✅ same split as design principle 13 |

## 3. Organising a 100+ item checklist

| option | evidence | verdict |
|---|---|---|
| One file per item, read directly by the agent | Not documented anywhere read. 100+ files means 100+ reads or a nested index→item hop, which BP warns gets partial reads | ❌ as the *load* shape |
| One file per domain, linked from SKILL.md | BP Pattern 2 (`reference/finance.md`, `sales.md`…); SC "Domain organization" (`aws.md`, `gcp.md`); AS "keep reference files focused" | ✅ as the load shape |
| Grep-able reference: SKILL.md tells the agent to `grep -i` the reference dir | BP Pattern 2 "Quick search" | ✅ cheap way to find one checkpoint by id |
| Files are truth, indexes derived; one concept per file for conflict-free parallel work | shelf constitution I–II (design principle 2) | ✅ as the *authoring* shape |
| Router / index for many items | MP SKILL-MECHANICS "Router skills"; K INDEX.md is hand-written and already drifts from the frontmatter descriptions | ✅ an index, ❌ hand-written |

**Reconciliation:** author one file per checkpoint (design principle 2 stands), and *project* them
by a script into one reference file per area (`references/<area>.md`, TOC at top, every checkpoint
under a heading named by its id) plus an index table inside SKILL.md. The agent makes one hop:
SKILL.md → area file. The checkpoint sources sit outside the load path, like ML's evidence.md.
Token risk R6 then shrinks to "largest area file + SKILL.md". Untested: whether 15–25 checkpoints per area stays under ~5k tokens per file.

## 4. Description, triggering, always-on cost

| claim | source | verdict |
|---|---|---|
| Description = what it does + when; third person (BP) vs imperative "Use this skill when…" (AS, SP) | BP; AS optimizing-descriptions; SP | ✅ "Use when…" — the two agree on content, differ on voice |
| Hard cap 1,024 chars (open standard); Claude Code truncates `description`+`when_to_use` at **1,536** in the listing | AS spec; CC | ✅ ≤1,024 for portability. M: `claude plugin validate` on a skills dir **passed** a 1,620-char description, so nothing in the toolchain enforces 1,024: needs a shelf fitness test |
| Listing budget = **1% of context window**; on overflow Claude Code drops descriptions of the least-invoked skills first | CC "Skill descriptions are cut short" | ✅ a rarely-run skill like blueprint is first to lose its description |
| Claude under-triggers; make descriptions "a little bit pushy" | SC; AS | untested for blueprint (see §4 verdict below) |
| **Never summarise the workflow in the description**: agents followed the description's summary and skipped the body's second review step | SP writing-skills (CSO); TH tip 6 | ✅ |
| Simple one-step tasks don't trigger skills regardless of description; only tasks the agent can't easily do alone | SC "How skill triggering works"; AS | ✅ a kickoff/audit is multi-step, so it is triggerable |
| One trigger per branch; synonyms of one branch are waste; front-load the leading word | MP writing-for-agents "Context pointers" | ✅ |
| Model-invoke only if the agent must reach the skill unprompted, or another skill must; else `disable-model-invocation: true` = zero always-on cost | MP SKILL-MECHANICS "Invocation"; CC frontmatter | ✅ — see recommendation 3 |
| Trigger eval: ~20 queries, 8–10 should / 8–10 near-miss should-not; 3 runs each; pass at rate 0.5; 60/40 train/validation split; pick best by validation; ~5 iterations | AS optimizing-descriptions; SC run_loop | ✅ if model-invoked |
| `claude plugin eval` grader `tool_used: Skill` measures trigger rate per case | CC troubleshooting; PE | ✅ |

Measured always-on cost (M, `claude plugin details`, 2026-10-10):

| plugin / skill | always-on | on invoke |
|---|---|---|
| skill-creator | ~110 tok | ~10.9k |
| k-my, all 23 skills | **~4,326 tok every session** | — |
| k-my my-language (2,000+ char description) | ~700 | ~10.5k |
| k-my code-to-spec | ~360 | ~3k |
| k-my products-picker | ~340 | ~12.5k |

Owner evidence on description work: code-to-spec's optimiser ended at best test 5/7, train 6/12
after 5 iterations (K optimizer.log). my-language calibration found skill-creator's `run_eval.py`
scored **0 triggers in 40 runs**, including positives the installed skill does fire on: it tests a
temporary slash command, which is never auto-invoked. "A harness that cannot detect a true positive
reports nothing, and its result is void" (ML calibration.md). Also: a prompt that needs no tool at
all cannot be reached by any description; only always-loaded text (CLAUDE.md / AGENTS.md) reaches it (ML).

## 5. Evals

| kind | how | source | verdict for blueprint |
|---|---|---|---|
| Trigger evals | should/should-not queries, trigger rate | AS; SC; PE `tool_used: Skill` | ✅ only if model-invoked |
| Task evals with/without skill | each case run with and without; report Δ | PE (3 runs/arm default); AS `iteration-N/with_skill,without_skill`; BP "baseline first" | ✅ Δ is the only number that says the skill helped |
| Fixture repos | `case.yaml` → `context.scaffold_script` (bash, runs as you outside the sandbox, only with `--scaffold`, ≤120 s, files and git state only; project config it writes is **not loaded**); `context.add_dirs`; otherwise each run starts in an empty dir | PE "Seed the workspace" | ✅ answers R7: a fixture repo = a scaffold script that builds it |
| Graders available | `regex`, `tool_used`, `tool_order`, `file_exists`, `llm` (2-of-3 judge votes), `baseline` (vs a reference transcript). **No custom-code graders** | PE grader types | ✅ — shapes the report format (rec. 8) |
| Grader stability | `llm` graders drift on long text; grade long files with `regex` over `{source: file, path: …}`; one grader on the result + one on the steps | PE "Choose graders that give a stable signal" | ✅ |
| Δ accounting | `tool_used: Skill` graders are excluded from score in both arms (reported only) | PE baseline | ✅ don't count "skill fired" as quality |
| CI | `--json`, `--threshold`, pin `--model` and `--judge-model`, `--max-cost-usd`, `--trust-plugin`; exit 0/1/2 | PE "Run evals in CI" | untested — cost per run unknown; keep out of `make check` (rec. 10) |
| Format collision | skill-creator's `evals/evals.json` and plugin-eval case dirs both default to `evals/`; "neither tool reads the other's case files" | PE intro; CC | ✅ pick plugin eval; move skill-creator work elsewhere or via `experimental.evals` |
| Assertions | add after first outputs; objectively checkable; PASS needs quoted evidence; drop assertions that pass in both arms; fix ones failing in both | AS evaluating-skills | ✅ |
| Cases only from observed failures, never predicted ones; "once a number exists it gets optimised against" | ML calibration.md | ✅ seed cases from a2kay/a2peer/lifesim known problems, not guesses |
| Every terseness check needs a fact-retention companion, or an empty reply scores perfect | ML calibration.md ② | ✅ blueprint analogue: every "finds the fault" case pairs with "passes the clean fixture" |
| Pressure scenarios + rationalisation tables for discipline skills; RED baseline before writing | SP writing-skills | ✅ for "✅ without proof" (checkbox theater) |
| Haiku/Sonnet/Opus all tested; ≥3 evals before sharing | BP checklist | untested — pick the models the owner runs |
| Superpowers splits `tests/` (non-LLM code) from `evals/` (live LLM sessions, 3–30+ min each, unsafe for public CI); static checks on PR, live sweeps nightly | SP docs/testing.md | ✅ same split as `make check` vs eval runs |

**Blocker (M):** local `claude --version` = **2.1.259**; PE requires **2.1.269+**. `eval` appears in
`claude plugin --help` but R7 cannot be trusted until `claude update`.

**Eval location (M + PE):** the suite lives in `evals/` *inside the plugin root*. Shelf's
`.claude-plugin/marketplace.json` declares one plugin `skills` with `source: "./"`, so the plugin root
is the repo root and the default suite would be `shelf/evals/`, shared by every future skill. To keep
cases under `skills/blueprint/evals/`, set `experimental.evals` on the marketplace entry (PR says an
entry accepts every manifest field) or pass `--eval-dir`. Untested.

## 6. Evolution — versions, lessons, decay

| practice | source | verdict |
|---|---|---|
| **Gotchas section** is the highest-value content; add every correction you had to make; keep it in SKILL.md, not a reference, because the agent may not recognise when to load it | AS best-practices "Gotchas"; TH tip 2 | ✅ |
| Capture successful approaches and mistakes into the skill; ask Claude to self-reflect when off track | BLOG | ✅ |
| Claude A writes / Claude B uses; watch B's file-read order, missed links, ignored files | BP "Observe how Claude navigates" | ✅ read eval transcripts for this |
| Regressions table: each observed failure gets a row (failure · rule · check) and a case | ML calibration.md R1–R10 | ✅ the anti-patterns file from design principle 12, in this shape |
| Mining script re-derives the evidence from transcripts; also catches drift in the rules' own source | ML mine.py | ✅ later: mine blueprint runs from transcripts for missed checkpoints |
| Stop hook that **logs, never blocks**: a blocking gate was measured to fire on 28% of 4,959 turns | ML hooks/my_language_lint.py | ✅ if a hook is ever added |
| Plugin hooks in `hooks/hooks.json` are inert when the skill is only symlinked into `~/.claude/skills/` | ML SKILL.md "Drift" | ✅ note for distribution |
| Time-sensitive rules → an "Old patterns" `<details>` block, not dated conditionals | BP | ✅ where an expired checkpoint goes before deletion |
| On a new model release, audit skills and remove deterministic instructions the model now follows | TH (podcast summary, secondhand) | ✅ a RECONCILE trigger |
| Lifecycle buckets `in-progress/` → promoted → `misc/` → `deprecated/`; only promoted ship | MP CLAUDE.md | ✅ maps to shelf `candidate` → active → deprecated |
| Changesets → CHANGELOG with the *why* per change | MP CHANGELOG.md | ✅ |
| Every docs page carries an "It's working if" section | MP CLAUDE.md | ✅ = blueprint's per-checkpoint `verify` |
| superpowers keeps a `CREATION-LOG.md` and `test-pressure-N.md` files inside the skill | SP systematic-debugging | ❌ inside the skill dir: they cost nothing until read, but they belong in the change folder / evals |
| Plugin `version` pins users until it changes; `claude plugin tag` makes `{name}--v{version}` tags | PR `version`; M `claude plugin --help` | untested: conflicts with shelf's `name-vX.Y.Z` tag rule, check before tagging |
| State in `${CLAUDE_PLUGIN_DATA}` (kept across updates); never in `${CLAUDE_PLUGIN_ROOT}` (replaced on update) | PR env vars; TH tip 7 | ✅ |

## 7. State across sessions and context loss

- SKILL.md is not re-read; compaction keeps its first 5,000 tokens; many invoked skills can push it out entirely (CC). ⇒ an audit spanning sessions cannot live in the agent's context.
- Copyable progress checklist in the response ("Copy this checklist and track progress") for multi-step work (BP, AS). ✅ for one session; ❌ as the cross-session record.
- Store state as logs/JSON/SQLite in `${CLAUDE_PLUGIN_DATA}`, not the skill dir (TH tip 7; PR). For blueprint the state is *about the target repo*, so it belongs in that repo or its beads, not in plugin data. ✅ supports F1 option (a).
- Resume rule: re-invoking the skill restores its content (CC troubleshooting). ✅ SKILL.md tells the agent to re-invoke after compaction and re-read state from beads + the report.
- `context: fork` runs the skill in a subagent without conversation history; background forks edit outside `/rewind` checkpoints (CC). ❌ for the main audit (it needs the owner's answers); untested for per-area fan-out.

## 8. Instruction wording

| finding | source | verdict |
|---|---|---|
| Composition prohibitions backfire: "don't restate the brief" → 4.4 re-typed values, worse than no guidance (3.6); a positive recipe → 3.0, zero variance; adding a nuance clause to the recipe → 3.8, noisy (opus, 5 reps) | SP positive-instruction spec 2026-06-10 | ✅ |
| Prohibitions that do work: tripwires on concrete tokens, recognition (red-flag) tables, discrete policy gates ("do not ask X to do Y") | same | ✅ "do not commit" stays a prohibition |
| Explain *why* instead of ALL-CAPS MUST; caps are a yellow flag | SC "Writing Style"; AS | ✅ every checkpoint already carries `why` |
| Defaults, not menus; one tool with an escape hatch | BP; AS | ✅ stack packs name one tool per job |
| Leading words: a pretrained concept repeated as a token anchors behaviour cheaply; prefer existing words to coinages | MP writing-for-agents | ✅ |
| Consistent terminology: one term per concept | BP | ✅ = design principle 10's two vocabularies |
| Match form to failure: skipped-under-pressure → red-flag table; wrong shape → positive recipe; missing element → required template field | SP writing-skills | ✅ |

## 9. Anti-patterns others documented

- Deep reference chains; Windows paths; too many options; time-sensitive text; magic constants; assuming tools are installed (BP).
- Workflow summary in the description (SP).
- Railroading: rigid step lists where goals and constraints would do (TH tip 4). Conflicts with BP's checklists: BP scopes checklists to "complex, multistep" fragile flows. Blueprint's audit loop is one; the content of each checkpoint is not.
- Overfitting descriptions to failed queries' keywords (AS optimizing-descriptions).
- Narrative examples tied to one session; generic labels (`step3`); code in flowcharts (SP).
- A trigger harness that cannot detect a true positive (ML calibration.md, skill-creator `run_eval.py`).
- An eval suite built from predicted failures (ML calibration.md).
- Name not matching the directory: `fable-council/SKILL.md` says `name: my-fable-council`; AS spec
  says the name must match the parent directory; `claude plugin details` lists it as `fable-council`
  without complaint (K, M). Nothing in the toolchain catches it, so a fitness test must.
- Hand-maintained skill index (K INDEX.md) restating descriptions that also live in frontmatter.
- Untrusted skills: audit scripts and network calls before install; `allowed-tools` applies even in untrusted folders (OV security; CC).

## 10. Owner's report-shape precedent (F2)

`micro-software` uses a closed verdict vocabulary "to keep agents comparable" (BUILD · ADOPT ·
KEEP+WRAP · DEFER · RIDE-ALONG · REJECTED) and two artifacts with different lifespans: a
point-in-time tree and a living ledger (K micro-software/SKILL.md "Verdict vocabulary", "Capturing
the output"). ✅ Same shape for blueprint: the four verdicts are the closed vocabulary; the report is
point-in-time; beads are the living ledger.

## Recommendations for blueprint

1. **Keep SKILL.md under 500 lines and put the resume rule, the four verdict words and the "not
   done" words in its first ~2,000 tokens.** Why: compaction keeps only the first 5,000 tokens of an
   invoked skill (CC), and the file is never re-read on later turns.
2. **Author one file per checkpoint; ship a generated `references/<area>.md` per area (TOC at top,
   one `## <id>` heading per checkpoint) plus a generated area index in SKILL.md.** Why: keeps design
   principle 2 and constitution I–II, while the agent makes the one hop BP requires and loads only
   areas in play. Add a fitness test that the projection is fresh.
3. **Ship v0.1 user-invoked (`disable-model-invocation: true`) and put the trigger in the
   consumer's AGENTS.md resolver block ("starting a repo or auditing its setup → run
   `/blueprint`").** Why: blueprint is started on purpose; a model-invoked description costs
   ~100–700 tok in every session in every repo (M) and is the first to be truncated when the 1%
   budget overflows (CC). It also removes the F6 description loop from v0.1. Flip it only after an
   observed miss, and only then run the 20-query near-miss loop (AS) against `onboard-consumer`,
   `init`, `micro-software`, `code-to-spec`. Tension with rec 5, untested: a user-invoked skill is
   removed from Claude's context (CC), so an eval prompt can reach it only as `/blueprint …`; confirm
   that a `claude plugin eval` run (non-interactive) expands a leading slash command before relying on it.
4. **If it is ever model-invoked: "Use when…", triggers only, no workflow summary, ≤1,024 chars,
   enforced by a shelf test.** Why: SP measured agents following the summary instead of the body;
   M showed `claude plugin validate` does not enforce 1,024.
5. **Use `claude plugin eval`, not skill-creator's `evals/evals.json`, as the one eval format.**
   Why: both default to `evals/` and neither reads the other (PE); plugin eval gives Δ vs no plugin,
   fixtures and CI exit codes. Run `claude update` first: local 2.1.259 < required 2.1.269 (M).
6. **Build each fixture repo with a `scaffold_script` (git init + files), run with `--scaffold`.**
   Why: the only supported way to seed a workspace (PE); config written by the scaffold is not
   loaded, which is what you want for an audit target.
7. **Pair every fault-finding case with a clean-fixture case.** Why: ML's fact-retention rule. A
   suite that only plants faults rewards an agent that marks everything "failing"; checkbox theater
   needs the reverse case too.
8. **Make the audit write a report file with one line per checkpoint: `<id> · <set up?> · <working?>
   · <evidence path or command>`, verdict words from the closed set.** Why: there are no code graders
   (PE); `regex` over a file is stable, `llm` on long text is not. A line per checkpoint makes
   "finds fault X" and "does not pass clean Y" single regexes. Add one `tool_used`/`tool_order`
   grader per case for the steps (e.g. `make check` was run before "passing" was written).
9. **Seed cases and the anti-patterns file only from observed failures** (a2kay, a2peer, lifesim
   known problems, owner corrections from R6), each as a regression row `failure · checkpoint ·
   check` plus an eval case. Why: ML calibration found every predicted failure wrong and every real
   one came from the owner; predicted cases get optimised against.
10. **Keep evals out of `make check`; run them on demand and before a tag, with pinned `--model`,
    `--judge-model` and `--max-cost-usd`.** Why: live runs are slow and cost money (SP testing.md,
    PE); `make check` keeps the static parts (frontmatter, projection freshness, description length).
11. **Write checkpoint `check` and `fix` fields as positive recipes; keep prohibitions only for
    policy gates and red-flag tables.** Why: SP measured composition prohibitions doing worse than
    no guidance and recipes reaching zero variance.
12. **Gotchas live in SKILL.md body (short), regressions in a separate file with the evidence.**
    Why: AS/TH name gotchas the highest-value content and say the agent may miss a gotcha behind a
    pointer; ML keeps measurements out of the load path in evidence.md.
13. **No scripts in v0.1; when transcripts show the same check re-written, extract to `tools/` with
    the AS script contract (JSON stdout, stderr diagnostics, documented exit codes, non-interactive,
    bounded output).** Why: SC/AS/BLOG all name repeated work as the signal; the contract is
    AS's.
14. **Version with shelf git tags and a CHANGELOG entry carrying the why; expired checkpoints move to
    an "old patterns" block, then are deleted at RECONCILE; re-audit the whole skill on each new
    model release.** Why: BP "old patterns", MP changesets, TH model-release audit; shelf already
    requires tags and decay. Check `claude plugin tag`'s `{name}--v{version}` format against the
    shelf tag rule before the first tag.
15. **Audit state lives in the target repo (beads + the report file), never in the skill dir or
    plugin data.** Why: SKILL.md content does not survive compaction intact (CC), skill dirs are
    replaced on update (PR), and the state describes the repo, not the user.
