# Fable round A — blueprint as software

Reviewer: Fable 5.1, 2026-10-10. Scope: the skill as software (structure, files, state, scripts,
trigger, evals, evolution, failure modes). Checklist *content* (C1–C8, F3, F4, F7, F8) is round B;
cited here only as evidence. Every claim below carries a verdict: **supported** (the files show
it) · **refuted** (the files show the opposite) · **untested** (needs a run). My own one-pass
findings are marked untested where I could not verify them against a primary source.

Files read: proposal, design, inventory, research/{skill-practices, plugin-tooling, prior-art,
repo-standards, owner-corrections, shelf-machinery}, docs/constitution, resolution 0014,
specs/skill-kind, onboard-consumer SKILL.md, shelf `pyproject.toml` / `Makefile` /
`tools/catalog.py` / `tests/test_gate_covers_every_skill.py` / `.claude-plugin/*.json`, and
k-my `my-language/{SKILL.md, calibration.md, mine.py}` + workspace `check.py`.

---

## 0. Ranked — the seven things that matter most

| # | finding | verdict | what to do |
|---|---|---|---|
| 1 | **The build order repeats the predecessor death.** Steps 1–3 (merge inventory → two Fable rounds → evals + three fixture repos) all precede any SKILL.md. Eight research files exist; zero checkpoints have run on a repo. Principle 11 ("no eval case → candidate") × ~160 checkpoints means the first real audit reports ~160 `not checked`. weiss: 3 spec revisions, 6 plans, no file written. | supported (design.md build order; prior-art §2, §4) | Step 0 is not "first", it is **v0.1**: ~15 checkpoints (gate + agents + shelf pillars), run for real on a2peer, lifesim and the shelf itself, tagged, before checkpoint 16 is authored. The other ~145 stay rows in `inventory.md` (no file, no template, no eval) until they run once. A checkpoint **earns its file by running**. |
| 2 | **Principle 5's reason is false in the repo.** It avoids scripts because "pyrefly `project-includes` and coverage `source` cover `packages/` only". True — and that means `tools/onboard/`, the precedent it cites as "verified mechanism", is **also outside the type gate and coverage today**. | supported (`pyproject.toml` L261 `project-includes = ["packages"]`, L390 `source = ["packages"]`; `tools/onboard/*.py` exists) | Extend the gate to `tools/` (one shelf bead, before blueprint). Then write the three scripts blueprint needs on day one (§4). Principle 5 keeps its *other* half: the checks themselves are never scripts. |
| 3 | **F1 is already decided by principle 3.** "An override counts as passing when it carries a fixed reason code plus free text, **checked into the repo**." That *is* a checked-in state file. Beads-only is internally inconsistent; and a bead closes, an override stands. | supported (design.md principle 3 vs F1 lean) | Decide (b): a small hand-written `blueprint.toml` (overrides + version pointer = truth) + a generated report (derived) + beads for the work. §3. |
| 4 | **Plugin version ≠ skill version.** `plugin.json` is `name: "skills", version: "0.1.0"` for every future skill; `claude plugin tag` would produce `skills--v0.1.0`. A repo's "audited against blueprint vX" cannot point at that. | supported (`.claude-plugin/plugin.json`; plugin-tooling §3) | The state file records a **checkpoint-set hash** (sorted active ids + each file's content hash). Re-audit diff = set difference, exact, independent of tag naming. F11 becomes cosmetic. |
| 5 | **Evals cannot run the real toolchain.** The eval sandbox withholds network except explicit `WebFetch(domain:)` grants; a python-uv fixture's `make check` needs `uv sync` + ruff/pyrefly/pytest. Scaffold: minimal env, 120 s, files and git state only. | supported (plugin-tooling §1 sandbox, scaffold); untested whether a pre-populated `.venv` in the scaffold survives | Two eval lanes, not one: **plugin-eval** cases use a *stub toolchain* (a Makefile whose targets call shell scripts that pass or fail on demand) and test the audit logic; **corpus runs** on real repos (shelf, a2peer, lifesim) test the real toolchain and are run by hand before a tag. §6. |
| 6 | **A full audit does not fit one eval case or one context.** `max_turns ≤ 200`, `timeout ≤ 3600 s`, ~160 checkpoints each needing a command and a line; a run that touches every pillar is a multi-hour session. | supported (plugin-tooling prompt.md limits; inventory size) | Blueprint takes a **scope argument** (`/blueprint gate`, `/blueprint all`). Cases are per pillar. One report file *per pillar* (constitution I–II: parallel fan-out must write disjoint files), projected into one view. |
| 7 | **Three taxonomies for one thing.** design.md: 5 phases × 25 pillars. inventory.md: 13 areas (`shape`, `ws`, `kb`, `shelf`, `stack`, `strict`, `arch`, `test`, `gate`, `agents`, `ops`…) that map to neither. Nothing joins them. | supported (design §Structure vs inventory headings) | Collapse **area into pillar** (pillars gain non-stack members: shape, naming, knowledge, agents). **Phase becomes a frontmatter field** of a checkpoint, not a tree level. Tree: `checkpoints/<pillar>/<id>.md`. §1. |

Everything below expands these and answers Q1–Q8 in order.

---

## 1. Structure (Q1)

### Sub-claims

| claim | verdict | why |
|---|---|---|
| Five layers each answer one question (when / point of view / what / how / why) | supported as *questions* | Good decomposition. |
| Five layers as a *file tree* | refuted | Phase and pillar are orthogonal; a checkpoint has one phase and one pillar. Two tree axes force a choice that is wrong either way. Phase = field. |
| 25 stack pillars | untested, likely over-split | 20–25 are tool slots a stack answers; fine for the stack pack. As the checkpoint grouping it leaves non-stack checkpoints (half the inventory) homeless. Add non-stack pillars; expect ~15–18 pillars total after merge (e.g. formatter+linter+types → `strictness`; coverage+mutation+property → `test-depth`). |
| "A stack pack is complete only when it answers every pillar" | supported | The strongest structural rule in the design. Make it a fitness test: `stacks/<stack>.md` has one `## <pillar>` section per stack pillar, each with the fixed fields or `not applicable: <reason>`. |
| Checkpoints are stack-neutral, read the stack answer for "how" | supported | Matches Scorecard probe ↔ ecosystem split. |
| Two verdict axes (set up? / working?) + not applicable + not checked | supported | weiss collapsed it and inverted the score; nothing caught it. The validator (§4) is what catches it here. |

### What makes an agent run it completely and identically — the run protocol

The agent cannot be trusted to enumerate. Enumeration and validation are mechanical; checking and
fixing are judgment. Fixed protocol, in SKILL.md's first screen (compaction keeps the first 5k
tokens):

```
0 ORIENT     detect stack(s) + repo kind; read blueprint.toml (overrides, last set hash)
             no stack detected (empty repo): run the decide-phase owner round first,
             write `stacks` into blueprint.toml, then enumerate — stack pillars cannot
             be listed without a stack
1 ENUMERATE  script → report skeleton: every applicable checkpoint, verdict `not checked`
2 CHECK      per line: run `verify`; write set-up · working · evidence (command + output ref)
             order: by phase; within a phase `where: gate` first (it is what proves the rest)
3 VALIDATE   script → refuses: missing line · verdict not in the closed set ·
             `passing` without evidence · `not checked` without reason ·
             override without reason code · override expired
4 REPORT     owner round: judge-type items batched per phase, principle 9 format
5 FIX        apply fixes, cheapest effort first; a fix with no re-check is still `failing`
6 RE-CHECK   step 2 on every fixed line; gate-type checkpoints prove red once
7 RECORD     write blueprint.toml (set hash, date); beads for every line still failing
```

Why this and not goals-and-constraints (TH tip 4 "railroading"): BP scopes checklists to fragile
multistep flows; an audit that must not skip is exactly that. The checkpoint *content* stays
judgment; the loop does not.

What stops faking ✅:

- Step 1 pre-fills `not checked`; the agent's only move is to *replace* lines. Skipping leaves
  `not checked` lines the validator rejects.
- `passing` needs an evidence string shaped `cmd: <command> → <summary>` or `path: <file>#<line>`.
  A `tool_used: Bash input_match <verify command>` grader on sampled checkpoints proves the command
  ran (§6).
- Gate-type checkpoints have two verify steps: *runs green* and *goes red on a planted violation*.
  `working = passing` requires both lines of evidence. This is principle 4 made mechanical.
- Judge-type checkpoints cannot reach `passing` without a recorded decision (the override file or
  a vault entry) — the validator checks the reference exists.

Identical every time: three eval runs per case, regex over the report; the only acceptable
variance is in free-text evidence, never in verdicts.

---

## 2. Files (Q2)

| claim | verdict | why |
|---|---|---|
| One file per checkpoint as authoring unit | supported | Constitution I–II; Scorecard `def.yml` precedent; expiry/eval per item. |
| Generated per-area reference as loading unit (F9) | supported, with one change | Project only what a *run* needs: `id · check · verify · fix · where · who`. `why`, `evidence`, `source`, `refused` stay in the source file, out of the load path, the way my-language keeps evidence.md out. Halves the loaded size. |
| Template fields (principle 2) | supported, restructure | Machine fields → YAML frontmatter; prose → body. Frontmatter is what the enumerator, validator, projection and fitness tests read. |
| "Too heavy?" | yes, for candidates | 11 fields × 160 files before any has run is the weiss spec trap. Active checkpoints get the full template; candidates are an inventory row. |
| Two gates, not one | supported (constitution V) | **File exists** = ran once on a real repo. **Active** = failed once on a real repo and the fix was applied = has a regressions row = has an eval case. Running alone earns a file, never activation; §7's "never fires → leaves" is this same rule read backwards. |
| Per-checkpoint `expires` | supported, with a default | 160 hand-set dates will not be maintained. Default by lifecycle: candidate expires 90 days after creation unless it runs on a real repo; active expires 180 days after its `evidence` date. RECONCILE reads the field, never sets it by hand. |

Proposed checkpoint file:

```yaml
---
id: gate.one-command
pillar: gate
phase: skeleton            # decide | spike | skeleton | thread | features
applies_to: ["*"]           # path globs; multi-stack repos match per path
where: gate                 # gate | audit | judge
who: agent                  # agent | owner
lifecycle: active           # candidate | active | deprecated
effort: low
expires: 2027-04-10
version: 2                  # bumped on any change that alters a verdict
verify:
  kind: command             # command | judge
  setup: "make -n check"
  working: "make check && <plant a violation> && ! make check"
source: [A-agt, L-fab, S]
evals: [gate-missing, gate-green-never-red, python-clean]
---
## Check
<what is true when it passes>
## Why
<what failed without it, with the number and the source>
## Fix
<the recipe, positive form; the template or patch if there is one>
## Refused
<deviations proposed by repos and rejected, with reason — so the next repo does not re-propose>
```

Fitness tests over the frontmatter (all in `make check`, no LLM): schema valid; `id` equals
path; every `active` has `evals` whose case dirs exist and whose graders mention the id; projection
(`references/<pillar>.md`, index table in SKILL.md) is fresh — `tools/catalog.py` +
`test_catalog_projection.py` is the exact precedent; description ≤ 1,024 chars (validate does
not enforce it: skill-practices §4).

---

## 3. State (Q3, F1 + R4)

**Decision: (b) — a checked-in state file, plus beads for the work. Not (a).**

| claim | verdict | why |
|---|---|---|
| "One job per system; beads already survives context loss" | refuted as an argument for beads-only | Beads hold *work*. An override is a standing *decision* with a reason code and an expiry; a bead is closed when done. The version pointer is neither. Three objects, three homes is "one job per system". |
| R4: Copier, cruft, projen all keep a checked-in version pointer; cruft records a rejected upstream change as a commit | supported | Three independent tools converged. |
| lifesim #32 wants `bootstrap.yaml` | supported in substance | Same thing under another name. |
| A generated report file (needed anyway for regex graders) | supported | It exists regardless of F1; the question is only whether a *truth* file sits beside it. |

Layout in the audited repo:

```
blueprint.toml            truth, hand-edited, small
  set_hash  = "sha256:…"  checkpoint set this repo was last audited against
  audited   = 2026-10-10
  stacks    = ["python-uv"]
  [[override]]
  id = "gate.container"; code = "not-applicable"; reason = "…"; expires = 2027-01-10
blueprint-report/<pillar>.md   derived, generated by the run, one line per checkpoint
beads  label blueprint:<id>   the work: every line still failing after step 6
```

Rules: overrides **expire** (the inventory demands `ws.ignore-expiry` of repos; blueprint must
meet its own bar; prior art's expiring ignore lists). Field ownership in `blueprint.toml`, so it
stays inside constitution I: the tool writes `set_hash`, `audited`, `stacks`; a human writes
`[[override]]` rows; the validator refuses a hand-edited tool field. Report files are
regenerated whole, never edited. `blueprint.toml` is validated by the same validator. The set hash gives a cheap
`check-update` (R4 #13): `tools/blueprint/diff.py --repo .` lists checkpoints added or changed
since — "re-audit these 7", not "re-run everything".

---

## 4. Mechanism vs judgment (Q4)

| claim | verdict | why |
|---|---|---|
| "No scripts in v0.1" | refuted for three scripts, supported for the checks | The predecessors stalled on *wrapping tools* and on *plumbing before value*. Enumerate/validate/project are not tool wrappers and are the thing that makes the report un-fakeable. Skipping them is how weiss's 9 of 16 controls violated their own contract unnoticed. |
| "Probes extracted when transcripts show repeated work" | supported | Keep for the *checks* (principle 14: prescribe config, never wrap tools). |
| "Code lives under `tools/`, tested from `tests/`, thin script in the skill" | supported | onboard-consumer precedent. Caveat: finding 2 — extend the gate to `tools/` first. |
| Plugin distribution of `tools/` | supported, untested in install | marketplace `source: "./"` makes the plugin root the repo root, so `${CLAUDE_PLUGIN_ROOT}/tools/blueprint/` ships with the plugin. Untested: whether an installed plugin copy carries the whole repo including `packages/`; if it does, that is weight, not breakage. |

Day-one scripts, `tools/blueprint/`:

| script | contract (AS script contract: JSON stdout, stderr diagnostics, exit codes, `--help`, idempotent) |
|---|---|
| `enumerate.py --repo . [--pillar p]` | reads frontmatter + detected stacks + `blueprint.toml`; writes the report skeleton(s); exit 0 |
| `validate.py --repo .` | the rules in §1 step 3; exit 1 with one line per violation, fix instruction in the message (harness's strongest trait); exit 2 = cannot read |
| `project.py` | `checkpoints/**` → `references/<pillar>.md` + SKILL.md index table; `make catalog`-style; drift test |
| `diff.py --repo .` | set hash vs current set → checkpoints to re-audit (§3) |

Not scripts, ever: running ruff/pyrefly/pytest/hadolint on the agent's behalf; parsing their
output; deciding a verdict. The `verify` field names the command; the repo's own `make check`
runs it.

---

## 5. Trigger (Q5, F6)

| claim | verdict | why |
|---|---|---|
| Ship v0.1 user-invoked (`disable-model-invocation: true`) | supported | Zero always-on cost; k-my already pays ~4.3k tokens/session; blueprint is the rarest-run skill and first to lose its description under the 1% listing budget. Started on purpose by a line in AGENTS.md and by `make bootstrap`'s final message. |
| Resolution 0014 scopes `Kind: skill` to push-based skills, so a user-invoked one does not fit | refuted as a blocker | 0014's tier split is about *standing cost vs discoverability*. A plugin-distributed, user-invoked skill has the plugin's distribution and tag mechanics with ~0 always-on cost. Amend 0014 by one line: Kind: skill governs plugin-distributed skills; invocation mode is a per-skill field; the budget assertion records both always-on (~0) and on-invoke. |
| Evals can reach a user-invoked skill via a `/blueprint …` prompt | untested — **build step 0, item 1** | CC docs: disable-model-invocation removes it from the model's context; whether `claude plugin eval` expands a leading slash command non-interactively is unknown. If it cannot: keep model-invocation on *during eval runs only* with the description set to the exact trigger phrase, or run evals against a copy without the flag (same body). Decide after the test, not before. |
| Also untested, same step | — | `evals/` location: default suite is `shelf/evals/` (plugin root = repo root) while skill-kind spec and `test_gate_covers_every_skill.py` expect `skills/blueprint/evals/` → `experimental.evals` or `--eval-dir`. Local Claude Code 2.1.259 < required 2.1.269: `claude update` first. |

Flip to model-invoked only after an observed miss; then the 20-query loop against
`onboard-consumer`, `init`, `micro-software`, `code-to-spec` (skill-practices rec 3).

---

## 6. Evals (Q6, F10)

Constraints that shape everything: no code graders; `regex` over `{source: file}` is stable, `llm`
on long text is not; sandbox has no toolchain network; scaffold ≤ 120 s, files only; two arms by
default; cost ≈ cases × runs × 2 + 3 judge calls per `llm` grader per run.

### Two lanes

| lane | what it tests | where it runs | cadence |
|---|---|---|---|
| **plugin-eval** | audit logic: enumerates, verifies, refuses to fake, applies fixes, validates | `claude plugin eval`, stub toolchain fixtures | before a tag; `--ablation none`, `runs: 1` while iterating; `with-without`, `runs: 3` pre-tag |
| **corpus** | the real toolchain and the real checkpoints | shelf, a2peer, lifesim, a2kay read-only; by hand or a Make target outside `make check` | before a tag; after a model release |

The stub toolchain: a fixture Makefile whose `check:` calls `tools/fake-ruff.sh` etc., each
reading `FAIL=1` from a planted file. The audit logic cannot tell it from the real thing, and
"goes red on a planted violation" is testable in-sandbox.

### Cases (seed only from observed failures — calibration.md's rule; a2kay, R6 rows, shelf gaps)

| case | fixture (scaffold) | planted | graders |
|---|---|---|---|
| `empty` | `git init` only; prompt declares the stack (`/blueprint all --stack python-uv`), since ORIENT's owner round cannot run in a non-interactive eval | everything | regex count: every applicable id present with `not set up`; `not checked` count:0; `file_exists` report. A second variant with no stack declared grades only non-stack ids plus the presence of the decide-phase question batch in `last_message` |
| `gate-green-never-red` | Makefile `check: true` | R6 row 32 (rule that cannot fire) | regex `gate.one-command · passing · failing`; `tool_used Bash input_match "make check"`; `tool_order` Bash before Write(report) |
| `hooks-configured-not-installed` | `.pre-commit-config.yaml`, no `.git/hooks` | R6 row 2 | regex `gate.hooks-installed · … · failing` |
| `ci-subset-of-local` | workflow runs lint only | R6 rows 1, 4 | regex `gate.local-covers-ci … failing` |
| `agents-md-dated` | AGENTS.md with a package count and a date | R6 row 11 | regex `agents.no-instance-data … failing` |
| `second-backlog` | `backlog.md` + `.beads/` | R6 row 20 | regex `kb.one-backlog … failing` |
| **`python-clean`** | full stub-green repo with `blueprint.toml` | nothing | regex: every id `passing`; `not set up|failing` count:0 — **the fact-retention companion; without it "mark everything failing" scores** |
| `override-honoured` | clean + one override `not-applicable` with reason + future expiry | — | regex `<id> · not applicable (not-applicable)`; validator exit 0 (`tool_used Bash input_match validate.py`) |
| `override-expired` | same, expiry in the past | — | regex `… failing`; validator exit 1 |
| `fix-applied` | `gate-green-never-red` + `--allow-tools Write Edit Bash` | — | `file_exists` on the fixed Makefile; one `llm` grader: "the Makefile was changed, not described as to-be-changed"; regex on report shows the re-check line |
| `scope-respected` | clean, prompt `/blueprint gate` | — | regex: no line from another pillar; `tool_used Read` max N (does not load other references) |

Each fault case is paired with the clean case. Each row in the regressions table (§7) is a case.

### Anti-gaming

- The report line is the only scored artifact; the validator refuses `passing` without
  evidence; a `tool_used` grader proves the verify command ran on sampled checkpoints.
- Clean fixture scores zero if anything is marked failing; fault fixture scores zero if the
  planted id is passing. Both arms, same regex set.
- `not checked` is a legal verdict only with a reason; a case with network-dependent verify
  grades `not checked (no network)` as correct, `passing` as wrong.
- Never a maturity score; the case score is the regex set, pass/fail per id.

### Cost

Non-judge graders everywhere but `fix-applied`; `--max-cost-usd` on every run; per-pillar
scope keeps `max_turns` under 60; docs sample is $0.41 for 6 runs of one case — a 12-case
suite at runs 3 × 2 arms ≈ $5–15, untested. Keep out of `make check`; `make eval` target.

### Static checks that *are* in `make check`

Frontmatter schema; `id` = path; every active id in ≥ 1 grader file; projection fresh;
description ≤ 1,024; `evals/` exists (already `test_gate_covers_every_skill.py`, gains the
population floor its docstring asks for).

---

## 7. Evolution and reabsorption (Q7)

The loop, concretely. Each row names the signal, where it is captured, the script that reads it,
and the decision it feeds.

| step | mechanism |
|---|---|
| **Capture at the run** | Every audit leaves three things in the repo: `blueprint.toml` (overrides with codes), the report, and a `## Blueprint lacks` section in the report: checkpoints the agent or owner wanted and did not find, one line each with the evidence. Nothing lives only in chat (`kb.homes` applied to blueprint itself). |
| **Reason codes are the signal** | `not-applicable` on one id across many repos → `applies_to` is wrong. `not-supported` (met another way) → the stack answer is incomplete or the checkpoint names a tool, not an effect. `not-detected` → the `verify` is wrong. `remediated` is noise. Closed codes make this countable; free text does not. |
| **Mining** | `tools/blueprint/mine.py`, shaped like my-language's: (a) walks consumer repos (the shelf knows them from `use-cases/`) and reads their `blueprint.toml` + reports → per-id verdict distribution, override counts by code, `lacks` lines; (b) walks `~/.claude/projects/**` transcripts for sessions where blueprint ran and counts owner pushback (`wtf`, `why didn't`, `you forgot`) within N turns of a checkpoint id — R6's method, automated. Prints **candidates, never verdicts**. |
| **Regressions table** | `skills/blueprint/regressions.md`: `failure · checkpoint · check · case`, one row per observed failure, each row an eval case. Rows enter after the failure happened once — never predicted. The anti-pattern list of principle 12 *is* this table. |
| **Deviation → rule or rejection** | A `lacks` line or a recurring override becomes a bead in the shelf labelled `blueprint-candidate`. RECONCILE decides: adopt (new checkpoint or `applies_to`/stack-answer edit, with the consumer repo as `evidence`), or reject — and the rejection is written into the checkpoint's `## Refused` section so the next repo does not re-propose it. Consumers never edit the shelf's checkpoints from their own repo. |
| **Never fires → leaves** | An active checkpoint `passing` in every audit for N runs (N untested; start at 10) either moved into repos' own gates (principle 13's goal: the audit shrinks) or never caught anything → delete. Böckeler's silent-sensor question, answered by counting. |
| **Expiry** | Defaults per lifecycle (§2). A candidate that never ran expires to deletion. An active one expires to re-justify: RECONCILE re-reads its evidence; if the evidence is one project (a2kay) and no second repo confirmed it, demote to candidate. |
| **RECONCILE cadence** | Before every tag; on every model release (TH: remove instructions the model now follows); when `mine.py` shows an override code climbing. It runs `mine.py`, walks the regressions table, prunes SKILL.md (MP "sprawl, sediment, no-ops"), re-runs `claude plugin details` into `catalog/blueprint.toml`. |
| **Versioning and re-audit** | Each checkpoint carries `version`; the set hash (§3) changes when any active checkpoint's content changes. A consumer's `make bootstrap-verify` (or the AGENTS.md resolver line) runs `diff.py` and prints "blueprint: 7 checkpoints changed since your last audit — run `/blueprint <pillars>`". CHANGELOG entry per change carrying the *why* (skill-kind spec requires it for trigger changes; extend to verdict-altering content changes). |
| **Consumer deviation that is right for one repo** | Stays an override with an expiry; it is a decision, recorded. "Right for every repo" is the shelf's call at RECONCILE, never the consumer's. |

What this loop does not do, on purpose: a blocking hook. my-language measured a pre-send gate
firing on 28% of turns; a session-start hook that *prints* "last audit N days old, set hash
behind" and exits 0 is the most it should do.

---

## 8. Failure modes (Q8)

Predecessors: harness wrapped tools and broke when flags changed; weiss built state, reconcile,
hashing, verbs and cascade before it could write one file, then stalled at a distribution plan;
both lived spec-first; the contract (`setup-unmet`) was violated by 9 of 16 controls and no
fixture caught it.

This plan's most likely stall, in order of likelihood:

1. **Authoring 160 full-template checkpoints with evals before any run** (finding 1). Same shape
   as weiss's spec-first death, just in Markdown. Compounded by "must not miss any point": the
   completeness demand and the earn-your-place rule pull in opposite directions, and the
   resolution is sequencing — complete *inventory*, incremental *activation*.
2. **Rot through the `fix` field.** Fixes carry tool-specific recipes; tools change flags;
   principle 14 protects the *checks* but the fixes still name commands. Mitigation: fixes
   prescribe config and Make targets, and the stack pack is the only place a tool invocation
   is written — one place to update per stack.
3. **a2kay overfit.** Half of the testing pillar's evidence is one repo with unverified numbers
   (research/a2kay-testing says several were overstated). Mitigation is already in principle 6
   and the demotion rule in §7.
4. **The report becomes the scaffold mode weiss wanted.** Fix content that is a template
   (Makefile, CI workflow) tempts a "regenerate from template" step — Copier's three-way merge
   by the back door. R4 #11 refuses it; keep it refused.

**The one move:** ship v0.1 from build step 0 with the gate pillar end to end — checkpoint files,
stub fixtures, the three scripts, run on a2peer and lifesim and the shelf itself, tagged — and
make "ran on a real repo" the condition for any further checkpoint's file to exist.

---

## 9. What you are not thinking about

| gap | verdict | consequence |
|---|---|---|
| **Dogfood: the shelf repo must pass blueprint.** shelf-machinery found five defects (4mz, 4f2, zox, dzl, 0h1). | supported | The shelf is corpus repo #1 and its own first fixture; a shelf that fails its own blueprint cannot dictate anyone's. |
| **An empty repo yields ~40 judge-type questions** (inventory: every `judge` row). Principle 9's format handles one question; nothing says how forty batch. | supported | One owner round per *phase* (decide, spike, skeleton…), the agent's default stated per item so "yes" accepts the batch; defaults recorded as the agent's. |
| **Multi-stack repos.** `applies_to: (stack, repo kind)` is per repo; a python API with a TS front end needs per-path stack detection and two stack answers. | supported | `applies_to` as path globs (§2); stack detection returns `{path → stack}`. |
| **Parallel fan-out writes one report.** If per-pillar subagents (`context: fork`) run, one report file is a merge conflict. | supported | One report file per pillar, projected (§3). |
| **`tools/` outside the type gate** (finding 2). | supported | A shelf bead before blueprint depends on it. |
| **Privacy of the report.** Evidence lines quote command output; on a public repo that can leak paths or names (`ws.privacy`). | untested | The validator runs the same PII needles the inventory demands of repos. |
| **The plugin ships the whole shelf.** `source: "./"` means an installed `skills` plugin is the repo. | untested | Measure install size once; if it matters, a `.claudeignore`-style exclusion or a separate plugin root is a later change, not v0.1. |
| **What the agent reads before it decides scope.** Step 0 ORIENT needs the index only (~1–2k tokens); it must not open `references/*` for pillars out of scope. | supported | The `scope-respected` eval case (§6) measures it. |
| **Resume after compaction.** SKILL.md is read once; the report *is* the resume state. | supported (skill-practices §7) | First screen of SKILL.md: "after compaction, re-invoke, read `blueprint-report/*.md`, continue from the first `not checked` line". |

---

## 10. Decisions, one line each

| q | decision |
|---|---|
| Q1 | Keep the five *questions*; tree is `checkpoints/<pillar>/<id>.md`, phase a field; fixed 8-step protocol with mechanical enumerate + validate. |
| Q2 | One file per checkpoint, frontmatter + body; projected per-pillar runbook (check·verify·fix only); candidates stay inventory rows until they run. |
| Q3 | (b): `blueprint.toml` (overrides with codes + expiry, set hash) + generated per-pillar reports + beads for work. |
| Q4 | Three scripts day one (enumerate, validate, project; diff soon after) under `tools/blueprint/`, gate extended to `tools/`; checks never scripted. |
| Q5 | User-invoked v0.1; amend 0014 by one line; `/blueprint` in eval prompt is build-step-0 item 1. |
| Q6 | Two lanes (plugin-eval with stub toolchain; corpus by hand); paired fault/clean cases; regex over report + tool_used/tool_order; ≤1 llm grader; per-pillar scope. |
| Q7 | Reason codes + `lacks` lines captured per run → `mine.py` candidates → regressions table → RECONCILE adopt/reject (rejection written into the checkpoint) → set-hash diff drives re-audit. |
| Q8 | Stall = authoring before running. Move = v0.1 is the gate pillar end to end on three real repos; a checkpoint earns its file by running. |
