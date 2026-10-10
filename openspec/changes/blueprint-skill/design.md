## Context

Design for `blueprint`, version 2 (2026-10-10). Version 1, with the reasoning trail it went
through, is kept at [research/design-v1.md](research/design-v1.md). This version folds in every
research pass, two Fable consults (advisory only, owner instruction 2026-10-10) and the lifesim
strategy handoff.

Decision marks: *owner* = his words or his "yes", with date · *agent* = the authoring session's
call, recorded so he can overrule · *Fable A/B* = adopted from a consult, with the file section.

### Inputs

| input | file |
|---|---|
| a2peer kickoff checklist | pasted in session; merged into [inventory.md](inventory.md) |
| lifesim bootstrap checklist + lifesim strategy handoff (phases A–E, provenance tiers, gate review, role table, anti-patterns 1–15, reversal table) | [research/lifesim-strategy.md](research/lifesim-strategy.md) |
| a2kay testing handoff, checked against the sources | [research/a2kay-testing.md](research/a2kay-testing.md) |
| shelf machinery, by path | [research/shelf-machinery.md](research/shelf-machinery.md) |
| prior art: agent-harness, agent-weiss | [research/prior-art.md](research/prior-art.md) |
| vault ontology, a2peer and lifesim as built, Makefile/CI/Docker conventions | [research/knowledge-and-kickoffs.md](research/knowledge-and-kickoffs.md) |
| external repo standards (Scorecard, Copier, Backstage, agent-readiness) | [research/repo-standards.md](research/repo-standards.md) |
| the owner's past corrections, 3,299 messages, 13 repos | [research/owner-corrections.md](research/owner-corrections.md) |
| skill-building practice; plugin eval / details / tag | [research/skill-practices.md](research/skill-practices.md), [research/plugin-tooling.md](research/plugin-tooling.md); distilled into [docs/skill-authoring.md](../../../docs/skill-authoring.md) |
| Fable round A (the skill as software) | [research/fable-round-a.md](research/fable-round-a.md) |
| Fable round B (the checklist's content) | [research/fable-round-b.md](research/fable-round-b.md) |

All research is one pass unless a file says otherwise.

## Status — 2026-10-10, end of the design session

Resume here after compaction. Work queue: `bd show shelf-1y4` (epic) and `bd ready`.

| part | state |
|---|---|
| design | done: D1-D18 + owner rounds 1-10 below; vocabulary in [CONTEXT.md](CONTEXT.md) |
| research | done: 13 files in `research/`, all one pass; two Fable consults (advisory only) |
| shelf prerequisites | done: `tools/` type-checked (shelf-yz4); resolution 0014 amended; plugin eval proven to reach a user-invoked skill; eval cases live in `evals/<skill>/` (plugin eval refuses them inside `skills/`); strict beads settings live in the shelf; onboarding's broken Makefile copy fixed (shelf-4mz) |
| blueprint code | v0.1 built: engine `packages/blueprint` (stdlib, one process, profile detection, overrides, set hash, reports, exit codes), gate concern (5 checkpoints) and backlog concern (7), each with a passing and a planted-violation test; `skills/blueprint/SKILL.md` with two paired eval cases; the shelf runs `make blueprint` in its own gate and passes it. Audit-only rows (`--audit`): clean clone, installed hooks, and the two that read bd's database |
| test speed | `make check` runs in a Linux container when Docker answers and tests only the packages a change reaches (`tools/affected.py`); `make check-all` runs everything and is what CI runs. Full gate 16m51s on the host → about 1 min in the container (2026-10-10) |
| consumers waiting | a2kay, lifesim, a2peer, homelab: unblocked by shelf-1y4.12 (corpus audits), which needs the engine, the gate and backlog concerns, and the skill |

Next: 1y4.12, audits of a2kay, lifesim, a2peer and homelab with `/blueprint`; then the remaining concerns one at a time.

## Owner round 10 — output contract (2026-10-10)

Owner: blueprint's output "should not be conversational… strict, structured, tables, properly tell
what is connected with what, aggressively terse"; highlight what matters to the human; reuse parts
of his `my-language` skill.

D18, the output contract every direction follows:
- Reports are tables, never prose: one row per checkpoint `id · concern · set up · working ·
  evidence · remediation · fixed by (auto / agent / owner)`.
- Connections are columns, not sentences: the concern, the ADR, the stack-profile row, the bead
  each finding links to.
- Only three things reach the owner in chat, after the report file is written: decisions that are
  his, mistakes that reached him, work ready for his yes (`my-language` agent-result rule).
- Status marks carry meaning only: ✅ passing · ❌ failing · ⚠️ needs the owner · 🔒 blocked; one per row.
- Large or structural change: a short plain-words explanation first; when much work is ahead,
  an Artifact page outlining all of it; anything structural drawn as a diagram — the target folder
  structure, the target layers, the target test structure, the main design (owner, round 10).
- From `my-language`: opener ≤10 words, one clause; every coined label glossed by its job on first
  use; a hedge survives shortening; a one-pass finding says so; the decision ramp (ground → shared →
  fork ✅/❌ → one-line question); word caps per message shape.

## Owner round 9 — how a run goes in a consumer (2026-10-10)

Owner, T3 summary: in lifesim you say "run blueprint"; the session fetches the shelf, finds the
blueprint skill and runs it against lifesim. **The first run only checks and finds problems**, and
produces an audit list. The agent then works out the best remediation for each; the script itself
may propose the fix, since most findings can be fixed mechanically. Remediations applied, lifesim's
`make check` passes. A month later, after blueprint has grown, the same run again.

| effect | |
|---|---|
| D6 run protocol splits in two | **audit**: orient → enumerate → check → validate → report, changes nothing in the repo · **remediate**: the report's remediation plan (each finding marked auto-fixable by script or needs-agent or needs-owner) shown first, applied after the owner's yes, then re-check and record |
| the engine proposes fixes | every check returns its remediation; a mechanical one carries a `fix` the engine can apply (`blueprint fix <id>`), so the agent's work is the non-mechanical rest |
| packaging | engine as `packages/blueprint/` (Kind `cli`); skill in `skills/blueprint/`; shelf audited by its own blueprint |
| per-commit checks | owner yes (round 10): each repo's own `make check` runs the fast scripted checks through a `blueprint` target; heavy checks (clean clone) run only in the audit |
| packaging | owner yes: engine moves to `packages/blueprint/` (Kind `cli`) |
| references | owner: blueprint is fundamental, so it is named in the shelf AGENTS.md and the owner's global instructions (done 2026-10-10); consumers get it through the resolver block once the skill exists |

## Owner round 8 — beads settings applied; one runner for all checks (2026-10-10)

| item | decision / fact | effect |
|---|---|---|
| beads strict set | owner yes to all; applied to the shelf and read back through `bd config show`: `no-git-ops`, `create.require-description`, `validation.on-create/on-close/metadata.mode = error` (branch, commit typed string), `export.auto/git-add = false`, `import.auto = false` | done in `.beads/config.yaml`; onboarding: shelf-no5 |
| `issues.jsonl` | owner: remove it | untracked and deleted; ignored. `interactions.jsonl` stays: bd documents it as its append-only audit log, "intended to be versioned in git", with no other copy |
| metrics in the cloud | owner wanted strict settings defined in the repo so cloud sessions get them. Measured: bd reads `metrics.disabled` **only** from the user config (source: "a repository can never re-enable metrics for a user who opted out"); a fresh home defaults to on; the env var `BD_DISABLE_METRICS=1` turns it off | the repo carries `env.BD_DISABLE_METRICS = "1"` in `.claude/settings.json`, so every Claude session in it, local or cloud, runs with metrics off. `config.local.yaml` adds nothing: the tracked `config.yaml` already travels with the repo. The doctor checks effective values, so any override fails it |
| checks architecture | owner: checks decomposed per concern/rule, but run together in one process, not one Python start per script; one surface the agent calls, driven by the repo's profile | `tools/blueprint/`: one runner; one module per concern; each check a function returning the common result; the runner selects checks by the repo profile (kind, surfaces, traits, stacks) and runs them in one process. Surface: `python3 <shelf>/tools/blueprint/run.py check [--concern X] [--json]`, behind `make blueprint` |

## Owner round 7 — deterministic checks first (2026-10-10)

Owner: "we need to have something like linting rules for as many things as possible, like make
check. We should not rely on AI to find it… run some scripts or maybe Rego… so that as many
findings of non-compliance will be detected deterministically, that's an ultimate strategy";
language: "whatever".

| decision | effect |
|---|---|
| **Every checkpoint whose verdict a program can decide is a script.** `where: judge` is allowed only with a written reason why no script can decide it | overrides D8's "the checks themselves are never scripted" (Fable A Q4) |
| **The checks run in each repo's own gate,** as one target (`make blueprint`) that `make check` depends on; resolved from the shelf clone the same way `guard` and `preset` are | non-compliance fails the commit that causes it, not the next audit; the AI audit is left with judge items and remediation |
| **Language: Python 3, standard library only** (*agent*; owner: "whatever") | the shelf's guard, preset and onboard tools already run as bare `python3` in consumers; testable with the gate's own pytest. ❌ Rego: needs the conftest Go binary, broke on JSON-with-comments in agent-harness, and resolution 0005 already chose native tests over OPA. ❌ Bash: untestable, and the zsh word-splitting trap tagged the wrong commit in a2kay. ❌ JavaScript: no Node in Python repos |
| **Checks read state; they never wrap tools.** A check reads config files, git state and tool exit codes; it never re-implements a linter (agent-harness stalled on that) | principle 14 stands |
| **One result shape for every check:** id · verdict (not set up / failing / passing / not applicable / not checked) · evidence · remediation command; JSON and one line per check for humans | the report files are generated from it; plugin eval grades them by regex |
| **Each check ships with a pass fixture and a planted-violation fixture,** run by the shelf's `make check` | "a gate never seen red is a hypothesis" |

## Owner round 6 — answers (2026-10-10)

| q | answer | effect |
|---|---|---|
| telemetry | off; blueprint must check it | done: `metrics.disabled = true`. bd stores this key only in the user-level `~/.config/bd/config.yaml` (it refused the repo file), so the check reads the user level; onboarding sets it (shelf-no5) |
| embedded mode | stay embedded for now; server mode soon | shelf-v01; a custom beads doctor meanwhile (shelf-xvf) |
| acceptance criteria | strict from the start: `error`, not `warn`; the config must be local to the repo where possible, and blueprint always checks it is set and strict | done in the shelf: `validation.on-create = error` in `.beads/config.yaml` (read back); `bd lint` in the gate and criteria for the 19 open beads: shelf-shq |
| more bd settings | "which other configuration items are available… I like strictness and being opinionated" | research running → [research/beads-config.md](research/beads-config.md) |

## Owner round 5 — answers and findings (2026-10-10)

| q | answer / finding | effect |
|---|---|---|
| ADR index | yes: Markdown ADRs with YAML frontmatter (`id`, `title`, `statement`, `concerns`, `status`, `decided_by` + tier, `updated`); generated `docs/adr/INDEX.md`, one line per accepted ADR grouped by concern; a script regenerates it and the gate fails when stale; AGENTS.md and `docs/agents/domain.md` point agents at the index only | fixed |
| seed ADRs | yes to the 8 | fixed |
| acceptance criteria | owner: every bead needs acceptance criteria before it is ready for work; how to enforce? Measured in a scratch repo: `validation.on-create = error` refuses a task without `## Acceptance Criteria`; `bd lint` exits 1 when an **open** bead lacks its sections and exits 0 for **deferred** ones | *agent* proposal: `validation.on-create = warn` (ideas can still be captured fast), `bd lint` in `make check` (nothing reaches open/ready without criteria; parked ideas stay deferred); the shelf has 19 open beads failing it today |
| embedded mode | `bd doctor` runs only against a dolt sql-server; the shelf uses beads' default embedded Dolt engine, so no health check runs | round 6 |
| telemetry | found: the user-level `~/.config/bd/config.yaml` has `metrics.disabled = false`, sending usage events to `gastownhall-eventsapi.com` | round 6 |

## Owner round 4 — answers (2026-10-10)

| q | owner's answer (T3 summary) | effect |
|---|---|---|
| tracker | beads with the mapping file | fixed; `docs/agents/issue-tracker.md` from [research/tracker-trial/issue-tracker-beads.md](research/tracker-trial/issue-tracker-beads.md) |
| workflow blind spots | wants the tracker workflow assessed for blind spots caused by misconfiguration | checked 2026-10-10: `bd ready` hides `shelf-b5j` and `bd blocked` lists it with both blockers — beads is right; the wrong status was in the markdown export. Found: `bd doctor` does not run in embedded mode ("not yet supported"), so the tracker has no health check; `bd lint` flags missing acceptance criteria on most beads. Both become backlog-concern checkpoints |
| ADR index | agents read one short index of decisions, a list of one-line statements each pointing to its ADR, never all ADRs; refreshed automatically by a script from ADR frontmatter; maybe YAML ADRs | round 5 Q1 |
| `docs/agents/` files | yes to the seven | fixed |

## Owner round 3 — answers (2026-10-10)

| q | owner's answer (T3 summary) | effect |
|---|---|---|
| culture files | all under `docs/agents/` | `docs/agents/constitution.md`, `docs/agents/<concern>.md`, plus Pocock's `issue-tracker.md` and `domain.md` there |
| other skills | blueprint may call other skills (Pocock's), notice a missing one and offer to install it, and adjust how those skills behave in a repo | blueprint configures them through `docs/agents/*` files, never by editing them |
| living ADR | yes to the shape: current decision on top, `## History` of dated changes with trigger and provenance tier | fixed |
| seed ADRs | seed each repo with a few key ADRs; later the shelf holds a shelf of ADRs that agents reuse **without copying**, as software is reused | v0.1 seeds a handful; "ADR shelf, referenced not copied" is a later change |
| tracker | doubts Pocock's local-markdown tracker; prefers to keep beads if it is better; asked for a side-by-side trial without removing beads | trial in [research/tracker-trial/](research/tracker-trial/); *agent* verdict: beads, with `docs/agents/issue-tracker.md` mapping Pocock's operations to `bd` |
| specs | unsure about specs as tracker items; "maybe it should write it in beads" | a spec is an epic bead; tickets are child beads with dependencies |

## Owner round 2 — answers (2026-10-10)

| q | owner's answer (T3 summary unless quoted) | effect |
|---|---|---|
| abstraction | "maybe we are overcomplicating things"; blueprint is higher-order bootstrapping, not a full blueprint of the software; technologies and frameworks change; framework-level answers (e.g. pagination in a FastAPI app) are not a bootstrapping concern; lessons absorbed later | stack profiles answer concern questions only (toolchain, gate, test carrier, architecture tool…); framework practice is out of v0.1 and enters through reabsorb |
| kinds | commit to kinds + surfaces + traits; note: a game may hold all logic in one process or split into server and client | surfaces are generic (server, CLI, UI); process topology is a trait, not a surface |
| glossary, ADRs | adopt Matt Pocock's conventions as his skills use and promote them: `CONTEXT.md`, `docs/adr/`, his numbering and format | root `CONTEXT.md`, `docs/adr/NNNN-slug.md` |
| lineage | not thousands of ADRs: change a decision inside its file and keep the lineage of the events and forces that led to each change in that same file; per concern and even for mini decisions; reusable across software | living ADR: one file per decision topic, history inside it (round 3 Q2 for the shape) |
| OpenSpec | blueprint prescribes the new way from v0.1; the shelf migrates as blueprint's first audit finding | this change finishes in OpenSpec; shelf migration is a finding |
| grill-with-docs | depend on skills; dependencies are a good strategy; skills will change and he may write his own | blueprint depends on Pocock's skills, never copies them |
| culture files (Q7) | yes to AGENTS.md managed block + `docs/constitution.md` + per-concern rule files | location: round 3 Q1 |
| hooks | ship the two existing ones only (SessionStart `bd prime`, Stop beads check); others much later | fixed |
| directions | start · audit · reabsorb | fixed |
| sub-skills | one entry point; sub-files called ad hoc; the agent knows of them once the skill loads | SKILL.md lists every sub-file with when to read it |
| interim path | left to the agent | *agent*: allowed and rare; ≤30 days; each is a bead with a due date; renewal needs the owner's yes; every run shows the open count |

## Owner round 1 — answers (2026-10-10), override the decisions below where they conflict

| q | owner's answer (T1 where quoted, else T3 summary) | effect |
|---|---|---|
| naming | "concern" is fine; rule: reuse accepted names from computer science, solution design and software development before coining | "pillar" → **concern** everywhere; vocabulary in [CONTEXT.md](CONTEXT.md) |
| conduct (D3) | reversed: "It's not enough to just set things up. It's important to set up a culture. A constitution even… and then reference this constitution in AgentsMD", maybe several files per concern; consistent file names, consistent AGENTS.md lines and consistent Claude hooks in every project | D3 replaced: blueprint installs culture as standard files with fixed names, pointed to by fixed AGENTS.md lines, and enforced by hooks where a hook can; not by grepping prose |
| one entry (D1) | yes; one skill, several directions (start, audit, …) sharing artefacts: the list of concerns with what to check, how, the remediation, and the links to stack profiles; a composite skill that tells the agent which file to go to | D1 stands, generalised to directions |
| repo kinds | backend apps (servers, MCP servers, CLIs); UI apps (front-end, desktop); library; game; infra. Open: how different is a game from a UI app, and infra from an app | round 2 |
| product design (D5/D10) | yes, inside; blueprint is "a collection of smaller subskills… instructions, registries", "one thing to rule them all"; absorb the best experience of building software and reabsorb from time to time. **OpenSpec no longer recommended; Matt Pocock's grill-with-docs instead**, embraced inside; an ADR ontology with lineage (what we used, decided, changed, what it impacted) | knowledge concern rebuilt around grill-with-docs (CONTEXT.md + ADRs) plus lineage; round 2 |
| testing (D13) | "forget about Gherkin": scenario-driven, feature and use-case driven testing; carrier is up to the stack; consistent within the same kind of repo and framework | D13: carrier per stack profile, fixed per profile |
| legacy (D9) | the agent says what can be done now, what is harder, and may offer an interim path; that should be rare; the skill "should force things… it's right move to spend some time today" | interim path = rare, expiring; default is remediate today |
| state (D7) | everything under one folder, `docs/blueprint/`; root not polluted | D7: `docs/blueprint/` holds config, overrides and reports |
| trigger (D14) | started by the owner when it makes sense; one simple AGENTS.md line is fine; likes `make bootstrap`-style hints, dislikes many comments; "a huge fan of things being opinionated" | D14 stands |
| restart (D12) | the owner decides; usually "not now — only critical things, then one by one"; brownfield expectation is incremental | D12 stands; default recommendation is incremental |
| corpus | a2kay, lifesim, a2peer, homelab; more later | corpus repos for the corpus eval lane |
| testing backlog | port a2kay's lesson: the gate in a Linux container to escape Microsoft Defender's scanning; and shrink the shelf suite the a2kay way (mutation-prune, refactor, scenario-based) | shelf-22x, shelf-b5j |

## Goals / Non-Goals

**Goals**
- Any repo, any stack: an agent runs blueprint and leaves the repo either passing each checkpoint
  or with a recorded reason why not. It misses no checkpoint and marks none passing without proof.
- A new repo is taken from "idea and owner" to "one thin thread of code under a green gate".
- Blueprint improves with every project that runs it.
- It costs nothing in sessions that do not use it.

**Non-Goals**
- Standing agent conduct (question format, escalation, worktrees, commit policy): see D3.
- Re-implementing what `make bootstrap` / onboard-consumer, the beads skill, openspec and
  `docs/agent-loop.md` already do. Blueprint runs them and checks their effect.
- Every stack on day one: a pack is written when its first project arrives.

---

## Decisions

### D1. One skill, one entry, three parts

| part | holds | cadence |
|---|---|---|
| **audit** | checkpoints: repo state an agent can verify by a command or a file | every run, idempotent |
| **kickoff** | the phases a new project goes through before and around code (D10) | once per repo, in order, with the owner |
| **review** | the gate-review procedure: lens audit, persona critique, blind re-audit (D11) | at each phase gate, and on blueprint's own audit output |

*Owner*, 2026-10-10: start and audit should not differ much, since an existing repo may need a
restart. *Fable B §3* showed that kickoff steps are a one-time workflow, not re-checkable state.
*Agent* reconciliation: one entry and one run protocol. On a repo with no kickoff artefacts, the
run starts with the kickoff; every kickoff step writes a file (a decision, a probe, a research
note) and the audit checks those files exist and are complete. The audit never re-asks a kickoff
question.

### D2. One taxonomy: pillar, selected by repo kind, answered by stack (Fable B §8)

| layer | question | where it lives |
|---|---|---|
| phase | when | a field on each checkpoint and kickoff step |
| **pillar** | from which point of view | the directory: `checkpoints/<pillar>/<id>.md` |
| checkpoint | what must be true | one file |
| stack answer | how, in this stack | `stacks/<stack>.md`, one row per pillar |
| evidence | why we believe it | in the checkpoint, with its grade (D5) |

- **Inventory areas collapse into pillars** (Fable A point 7). A pillar exists only if a checkpoint
  reads it.
- **Repo kind picks the pillar set:** app · library · CLI · game · infra. Stack answers the set.
  Without this axis an infra repo is ~11 "not applicable" rows and agents learn to type n/a by
  reflex (Fable B §8.4).
- **A stack cell has three states:** answered (names the repo that proves it) · not applicable
  (with reason) · untested. A pack is complete when no cell is empty; untested cells are shown.
  This keeps "extracted, never invented" for packs written from one project.
- **Multi-stack repos:** `applies_to` is a path glob; stack detection returns `{path → stack}`.

**Stack pillars** (19, after Fable B §8.2–8.3):

| # | pillar | python-uv answer (shelf) |
|---|---|---|
| 1 | toolchain and version pin | `.python-version`, `requires-python` |
| 2 | dependencies, lockfile, frozen install | uv, `uv.lock`, `uv sync --frozen`, upper bounds (RG004) |
| 3 | build and artifact | none (honest n/a) |
| 4 | task runner and gate word | make, `make check` |
| 5 | formatter | ruff format |
| 6 | linter, strictest preset | ruff, shelf preset, `make preset` |
| 7 | types / compiler strictness | pyrefly strict |
| 8 | architecture enforcement | import-linter or tach, chosen once (Fable B C2: resolution 0005 bans an external policy engine, not an in-toolchain tool) — untested, needs a shelf bead |
| 9 | test runner, parallelism, test kinds (tables, property, golden) | pytest, xdist (untested), Hypothesis |
| 10 | actor-surface scenarios and their in-process driver | pytest-bdd <9 + shelf `bdd-tags`, `mcp-steps`, `json-match` |
| 11 | isolation: env, clock, randomness, process seams | autouse hermetic conftest; shelf `testing` modules |
| 12 | coverage (incl. child processes) | pytest-cov, branch, low ratchet + diff-coverage |
| 13 | dependency hygiene | deptry |
| 14 | dependency vulnerabilities | osv-scanner (untested) |
| 15 | hooks | shelf installer; one manager |
| 16 | CI | one reusable workflow calling `make check` (a2web `gate.yml`) |
| 17 | packaging, release, install | git tags, `uv tool install` |
| 18 | config, secrets loading, validation strictness | shelf `settings-base`; pydantic strict |
| 19 | errors, logs, traces | shelf `a2effect`; structured logs + OpenTelemetry |

Candidate pillars (counted, not required until a checkpoint reads them): mutation testing,
persistence and migrations, workspace / monorepo layout, dev host and target OS.
Universal tools, answered once outside the packs: codespell, gitleaks.

**Non-stack pillars:** security (secrets, PII, visibility) · gate (clean clone, one command, CI
parity, guards proven red) · decisions and knowledge · backlog · agent instructions · shelf · review.

Every stack answer carries: tool and pinned version · config location · strictest settings and
why · target that runs it · its planted-violation test · output format for agents · wall time on
the reference machine · alternatives refused, with reason · the five proofs (D10) · proving repo ·
cell state.

The lifesim role table (strategy §5.4) is the template for deriving a new pack: fill the five
proofs per candidate tool with registry release dates on the day; a blank cell is a risk to log,
not a reason to skip.

### D3. Conduct leaves blueprint (Fable B §3.1) — *owner to confirm*

21 inventory items are standing conduct checked by grepping AGENTS.md prose (question format,
escalation, worktrees, commit policy, bug-on-sight, promote triggers…). A sentence does not make
an agent ask numbered questions, and always-loaded prose is cost (owner row 18: 36k tokens).
They move to where conduct lives: the shelf resolver block, `docs/agent-loop.md`, the owner's
global instructions; a hook where one can enforce it. Blueprint's only conduct check: the resolver
block is present and current (onboard-consumer's `verify` already does it).

### D4. The checkpoint file

```
checkpoints/<pillar>/<id>.md
---
id: gate.clean-clone
pillar: gate
phase: bootstrap
repo_kinds: [app, library, cli, game, infra]
applies_to: ["**"]                  # path globs
where: gate | audit | judge         # gate = the repo's own check fails without it
decides: owner | agent
lifecycle: candidate | active       # candidate: shown, not counted
expires: 2027-04-10
evidence_grade: measured | prediction | owner | external-one-pass
effort: S | M | L
---
## Check      what is true when it passes (a positive recipe)
## Verify     the command, or the judgment question; the proof it demands
## Fix        the steps the agent applies
## Why        the failure it prevents, with its evidence and source
## Refused    alternatives and rejected changes, with reasons
```

The generated per-pillar runbook (`references/<pillar>.md`, what the agent loads) carries only
Check · Verify · Fix. Why, evidence and Refused stay out of the load path (Fable A Q2).

### D5. Verdicts, overrides, evidence grades

- **Per checkpoint, two questions** (agent-weiss): *set up?* and *working?* Verdict words: not set
  up · failing · passing · not applicable · not checked (the check could not run). An empty repo is
  "not set up" everywhere.
- **Overrides** count as passing only with a reason code (test-data · remediated · not-applicable ·
  not-supported · not-detected, after Scorecard) + text + expiry, in `blueprint.toml`.
- **Work statuses** (beads, kickoff steps) never share a word with verdicts: untested · blocked on
  owner · broken · deferred (with trigger) · drafted, unverified (a fix never seen green is a
  hypothesis — lifesim §11).
- **Evidence grades:** measured · supported by prediction (Fable B §0: the a2kay testing remedy;
  confirm by classifying a2kay's next 30 closed bugs by the test that turned red first) · owner ·
  external, one pass.
- **Decision provenance tiers** (lifesim §1): T1 verbatim · T2 "yes" to a recommendation worded so
  yes accepts it · T3 relayed, wording reconstructed · T4 session decision. Every decision record
  carries its tier.

### D6. Run protocol (Fable A Q1)

1. **Orient** — read `blueprint.toml` and the reports if present; detect repo kind and `{path →
   stack}`; decide scope (`/blueprint`, or `/blueprint <pillar>`).
2. **Enumerate** (script) — the checkpoints for this kind, stacks and scope, as the report
   skeleton, every line "not checked".
3. **Check** — each line: run Verify, record set up? / working? and the evidence.
4. **Validate** (script) — refuses "passing" without evidence, "not checked" without a reason, an
   expired override, PII in evidence lines.
5. **Report** — one line per checkpoint in `blueprint-report/<pillar>.md`.
6. **Fix** — apply Fix for failing lines in the order of D9; judge items go to the owner as one
   batched round per phase, each with the agent's default so "yes" accepts it.
7. **Re-check** — re-run Verify for every fixed line.
8. **Record** — update `blueprint.toml` (set hash, overrides), file a bead per remaining failing
   line, and append "blueprint lacks: …" lines for anything the run met that no checkpoint covers.

Resume rule (first screen of SKILL.md): after compaction, re-invoke `/blueprint`, read the
reports, continue from the first "not checked" line.

### D7. State (Fable A Q3; reverses v1's lean)

In the target repo: `blueprint.toml` (checkpoint-set hash audited against, overrides with codes and
expiry; tool-owned and human-owned fields separated) · `blueprint-report/<pillar>.md` (generated) ·
beads for the work. Re-audit after a blueprint change = diff of the set hash (Copier/cruft keep the
same pointer, R4). Plugin version cannot serve: `plugin.json` is `skills 0.1.0` for every shelf
skill (Fable A point 4).

### D8. Mechanism: scripts under `tools/blueprint/` (Fable A Q4)

Day one: `enumerate`, `validate`, `project` (checkpoint files → per-pillar runbooks + index);
`diff` (set hash) soon after. The checks themselves are never scripted, and tools are never wrapped
(agent-harness broke on that). Prerequisite: shelf-yz4 brings `tools/` inside pyrefly and coverage.
Script contract from `docs/skill-authoring.md` §6.

### D9. Ordering (Fable B §6)

**New repo:** folder, git, visibility, secrets scheme, remote → kickoff phases A–C (each step
writes a vault file) → pins, lockfile, `bootstrap` target, fresh clone green with zero code → the
gate on an empty project, every guard proven red → AGENTS.md as a map, knowledge homes wired →
the thin thread → features, each scenario first. Everything that will later block a commit is
installed before the first line of code.

**Existing repo:** secrets and PII in tree and history → the gate exists at current strictness
(one command, CI, hooks) → pins and lockfile → strictness as ratchets, one whole-repo commit per
tool; on a large legacy repo the one legal carve-out is a dated suppression file, path-scoped,
each entry with a reason and an expiry (said so in the Definition of Done text) → actor-surface
scenarios for the journeys, journey coverage measured → architecture rules declared from reality
with dated allowlists, then tightened; unit-test pruning only after scenarios exist → AGENTS.md as
a map → the restart-or-migrate signals table to the owner (D12).

### D10. Kickoff phases (lifesim strategy §2–5)

| phase | exit gate | writes |
|---|---|---|
| A Discover | a one-page vision; every proposed feature can be refused by citing a pillar; gate review passed | vision, pillars, options, glossary, question tree |
| B Decide | every pick cites the five proofs; every decision has its provenance tier; nothing chosen from memory | research (Findings first, criterion named before the verdict), decisions, refused options |
| C Spike | every number a decision rests on is measured on the target machine; written verdict with conditions | probe files with outcomes registered before the run, platform-catches entries |
| D Bootstrap | the gate is green; each guard seen red once; each fix seen green | skeleton, strict tooling, banned-API lists, architecture tests, scenario runner, per-folder AGENTS.md |
| E Build | the thin thread: one scenario, one golden log, one architecture test, one property test, one save/load round trip | the thread; then a module per domain area, scenario first |

Rules carried from lifesim, each with its reason in the strategy file: frontier-only questions ·
find facts yourself · numbers never in design files, name the knob · a prototype binds nothing ·
state the criterion before the verdict · the five proofs (compatible · used together · models
trained on it · real use incl. complaints · shipped track record) · adopt a library on written
conditions tied to tests · decide the determinism contract (required / preferred / allowed) and keep
a platform-catches log from the first spike · store records, render prose · run in one process
first behind the boundary a split will use · round-trip test in the thread · mutation-check the
scenario runner.

Game-specific items (layered game design, ECS, utility AI, wake-up queue) go to a `game` repo-kind
note with their general form beside them, never into the universal core.

### D11. Review procedure (lifesim strategy §3.2)

Lens audit (one fixed question, fixed output block, a finding without a file is dropped) · persona
critique (one fresh subagent per persona) · blind re-audit (fresh subagent, only the file list and
the Test-for lines; every disagreement goes to the owner) · hash-pinned scope (`git hash-object` of
every file read; any changed hash means a full review). Applied at each kickoff gate and, as a blind
re-audit, to blueprint's own report before "done".

### D12. Restart vs migrate (Fable B §2)

The audit never recommends a restart. It outputs the signals (journey coverage, in-process
drivability, DAG violations vs modules, strict-gate error spread, persisted data and migrations,
external consumers, owner statement) and the owner decides. Restart is a strangler: scenarios green
on the old code → new skeleton beside it → same scenarios green on the new → old deleted. Below
roughly half journey coverage the only move is writing scenarios against live behaviour
(`k-my:code-to-spec`). Both owner restart rulings (R6) came from pre-user repos; persisted data
and external consumers are what make a restart unsafe.

### D13. Testing doctrine, stack-neutral (Fable B §1)

Universal: behaviour tested at the actor's real surface, in process, before the code · a
controlled vocabulary with a checker · a placement table; extend before create; never name a file
after a change · hermetic by default · fake below your own policy, at the process boundary · every
hermetic test in the gate, no nightly-only suites · flaky is a bug, retries banned · parallel-safe.
The **carrier is per pack**: Gherkin where steps are shared (python-uv); text scenario files plus
golden logs where scenarios are statistical or replay-shaped (lifesim, owner-accepted T2: "take
the owner's purpose, not the example tool"). All of it graded "supported by prediction" until the
a2kay 30-bug check runs.

### D14. Trigger and distribution (Fable A Q5)

User-invoked (`disable-model-invocation: true`): zero always-on cost. Reached by `/blueprint`, by a
line in each consumer's resolver block, and from `make bootstrap`'s output. Amend resolution 0014
by one line: Kind skill = plugin-distributed; invocation mode is per skill.

### D15. Evals (Fable A Q6, docs/skill-authoring.md §7)

Two lanes. **Plugin eval** tests the audit logic on scaffolded fixture repos with stub toolchains
(the sandbox has no network for real ones): paired fault/clean cases seeded only from observed
failures; regex over the report files plus `tool_used`/`tool_order`; at most one llm grader;
`--ablation none --runs 1` while iterating, two arms × 3 runs before a tag. **Corpus lane**: real
audits of the shelf, a2peer and lifesim with the real toolchain, by hand. Static checks in
`make check`: checkpoint schema, projections fresh, every active id covered by a grader,
description ≤1,024 chars, name = directory.

### D16. Evolution loop (Fable A Q7)

Each run records override codes and "blueprint lacks" lines → `tools/blueprint/mine.py` reads
consumers' `blueprint.toml` files and transcripts and proposes candidates → a regressions table
(failure · checkpoint · check), each row an eval case → RECONCILE adopts or rejects; a rejection is
written into the checkpoint's Refused section → the set-hash diff tells every consumer which
checkpoints to re-audit. A session hook may log; it never blocks. A checkpoint earns its file by
running on a real repo, and earns `active` by failing once with its fix applied (that failure is its
regression row and eval case). On each new model release, re-audit for rules the model now follows
unprompted.

### D17. Proposals carried, not adopted

- **Documentation ontology** (lifesim §8): each replaceable technology bound in one component row
  and one decision; technology names allowed only in listed places; a lint. Unaccepted by the owner
  in lifesim (Q1–Q8 open). Ships as `proposals/documentation-ontology.md`.
- **Decision records** (owner, 2026-10-10): a2kay kernel shape (decision · option · probe in v0.1,
  pack version pinned), `decided_by`, provenance tier, `superseded_by`, rejected options with
  reasons; a frontmatter gate until `a2kay validate` ships (`a2kay-fmj1`). Lifesim's extra fields
  (`about`, `derived_from`) become a declared overlay.

---

## v0.1

**Scope.** The gate pillar end to end first (Fable A point 1), then the rest of Fable B's fifteen:

| # | checkpoint | pillar |
|---|---|---|
| 1 | `gate.clean-clone` — fresh clone, `bootstrap`, `check` green, wall time against a recorded budget | gate |
| 2 | `gate.one-command` — one gate word; hooks and CI call it | gate |
| 3 | `gate.ci` — CI runs the same command; actions pinned; "no CI" needs a revisit trigger | gate |
| 4 | `gate.one-hook-manager` — one hook owner, beads chained, proven by a real commit | gate |
| 5 | `gate.guards-have-red-tests` — every guard has a planted-violation test | gate |
| 6 | `strict.preset` — strictest preset whole; one formatter; suppressions in one file with reason and expiry | linter |
| 7 | `arch.dag` — layers declared once, enforced by a tool that reads that file | architecture |
| 8 | `test.actor-surface-first` (prediction) | scenarios |
| 9 | `test.hermetic` — no network, parallel-safe, retries banned | isolation |
| 10 | `test.placement` | scenarios |
| 11 | `test.lanes` — every hermetic test in the gate | test runner |
| 12 | `stack.pins` — toolchain file, lockfile frozen, upper bounds | toolchain |
| 13 | `ws.secrets` — ignored, gitleaks tree + history, visibility recorded before the first push | security |
| 14 | `agents.one-file` — AGENTS.md canonical, a map, no dated data, context measured | agent instructions |
| 15 | `kb.homes` — beads only, decision files with the frontmatter gate, one home for requirements | knowledge |

**Constraint:** POSIX hosts in v0.1 (*agent*; Fable B §7 found six checkpoints that break on
Windows). Windows is the trigger for lifesim's pack.

**Packs in v0.1:** `python-uv` (evidenced) and `dotnet` (owner, 2026-10-10: written now, provisional;
from lifesim, most cells "untested").

## Build order

0. **Prerequisites:** shelf-yz4 (`tools/` in the gate); amend resolution 0014 for D14 through the
   resolutions flow (`docs/resolutions/README.md`, `Distilled into:` line); confirm plugin eval reaches a
   `/blueprint` user-invoked skill; eval dir location (`experimental.evals` or `--eval-dir`); tag
   format (`skills--v…` vs the shelf rule).
1. **Gate pillar end to end:** checkpoints 1–5 as files; `tools/blueprint/` enumerate + validate +
   project with tests; SKILL.md with the run protocol; run on the shelf (it must pass its own
   blueprint — five known defects: shelf-4mz, 4f2, zox, dzl, 0h1), then a2peer and lifesim; each
   checkpoint seen failing and fixed once; one paired eval case each.
2. Checkpoints 6–15, the same way, one pillar at a time.
3. Kickoff (D10) and review (D11) as phase docs; the python-uv and dotnet packs.
4. Evolution tooling: `diff`, `mine.py`, regressions table.
5. `claude plugin details` figure into `catalog/blueprint.toml`; population floor in
   `tests/test_gate_covers_every_skill.py`; `make check` green; tag on the owner's approval.

## Risks / Trade-offs

- **Stalling like agent-weiss** (authoring before running) → a checkpoint earns its file by running.
- **The testing doctrine rests on a prediction** → graded so; the a2kay 30-bug check confirms or
  refutes it.
- **Checkbox theater** → the validate script, paired clean fixtures, blind re-audit of the report.
- **Packs invented from one project** → the untested cell state and the proving-repo field.
- **The shelf fails its own blueprint** → it is corpus repo one; its defects are filed.
- **Report evidence leaks names** → the validator's PII check.
- **The plugin ships the whole shelf repo** (`source: "./"`) → measure install size once; a
  separate plugin root is a later change.

## Open questions (owner)

1. **D3 — conduct out of blueprint?** 21 standing-behaviour items (question format, escalation,
   worktrees, commit policy…) move to the resolver block, `docs/agent-loop.md` and your global
   instructions; blueprint checks only that the resolver block is current. Recommendation: yes.
