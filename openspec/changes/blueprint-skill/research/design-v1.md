## Context

This file is the **strategy for building blueprint**, written before any skill content. It names
the design decisions, the research each decision waits on, the topics to put to Fable, and the
build order. Decisions marked *agent* are the authoring session's and can be overruled; decisions
marked *owner* carry his words and date.

Inputs already in hand:

| input | what it gives | state |
|---|---|---|
| a2peer kickoff checklist (2026-10-10) | 11 areas, owner (D) vs agent (+) items | pasted in session |
| lifesim bootstrap checklist (2026-10-10) | 47 items incl. §6–7: how the skill itself should work | pasted in session |
| the a2kay testing handoff (session input) | a2kay testing doctrine, agent friction, Addendum 2 (orchestration, owner, edge cases, still-open) | read; numbers unverified |
| shelf machinery map | every tool, target, fitness test, testing package, by path | done: [research/shelf-machinery.md](research/shelf-machinery.md) |
| a2kay sources | evidence behind the testing rules | done: [research/a2kay-testing.md](research/a2kay-testing.md). a2kay's setup is spread over four unmerged places (`spike/pytest-bdd`, `spike/lineage`, `spike/mzfh`, an uncommitted worktree); several handoff numbers are stronger than the sources (listed in the file) |
| `agent-weiss`, `agent-harness` | the owner's earlier attempts at the same skill (2026-04) | done: [research/prior-art.md](research/prior-art.md); findings folded into principles 3, 13–15 and the build order |
| a2kay vault kinds; a2peer, lifesim as built; Makefile/CI/Docker conventions across repos | the knowledge area and the gate area | done: [research/knowledge-and-kickoffs.md](research/knowledge-and-kickoffs.md); folded into F7, F8 |

## Goals / Non-Goals

**Goals**
- One checklist an agent can run on any repo and not miss a point: every checkpoint has a verdict,
  a reason, and evidence.
- The checklist improves with use: a project that hits a missing or wrong checkpoint feeds it back.
- Low standing cost: the always-on description is small; detail loads only for the area and stack
  in use.

**Non-Goals**
- Re-implementing wiring that `onboard-consumer` / `make bootstrap` already verify.
- Teaching orchestration of many agents (see proposal, Scope).
- Covering every tech stack on day one.

## Design principles (decided, *agent*, unless marked)

1. **One checklist, one mode** (*owner*, 2026-10-10). Audit is the only mode; a new repo starts
   with every checkpoint failing. A new repo also gets the phase order (decide → spike → skeleton →
   one thin thread through every layer → features) and templates.
2. **A checkpoint is the unit.** ✅ One file per checkpoint with a fixed template, and an index
   that is generated, never hand-edited (constitution I–II applied to the skill itself). Template:
   `id · check (what is true when it passes) · why (what failed without it) · evidence (source,
   number) · verify (a command, or the judgment question) · where enforced (gate / audit / judge)
   · who decides (owner / agent) · applies to (stack, repo kind) · fix + effort · lifecycle
   (candidate: shown, does not count — Cortex's scheduled start, OpsLevel's "Enable Later" —
   or stable) · expires`.
   ❌ One long checklist file: parallel authors collide in it, and one checkpoint cannot evolve,
   expire or be evaled alone. Risk to check in R6: the index plus the files an audit opens must
   stay within the token budget.
3. **Two questions per checkpoint, taken from agent-weiss:** *set up?* (the config, file or target
   exists) and *working?* (it passes, or fails when it should). Verdicts: not set up / failing /
   passing / not applicable / not checked (the check could not run — never folded into passing or
   failing; Scorecard's `NotAvailable`, the Best Practices badge's `?`). An override counts as
   passing when it carries a fixed reason code plus free text, checked into the repo (codes after
   Scorecard's `scorecard.yml`: test-data, remediated, not-applicable, not-supported,
   not-detected). An empty repo is "not set up" everywhere and has no "working" verdicts. ❌ one verdict
   per checkpoint: weiss's spec had this split, its code collapsed it, and a missing AGENTS.md then
   scored set-up 100 / working 0 — the reverse of the truth. Nothing caught it because the pass and
   fail fixture repos the spec called for were never built.
4. **A check proves the effect, never the artifact.** `make check` exists ≠ `make check` fails on a
   planted violation. Every gate-type checkpoint names how it was seen red once (lifesim #19,
   onboard-consumer's `Result.verified`).
5. **Judgment in the skill, mechanism in tools.** v0.1 ships no probe scripts: checkpoints carry
   commands the agent runs. Probes are extracted when eval transcripts show agents re-writing the
   same check (skill-creator's own signal). When they come, they follow `onboard-consumer`: a real
   module under `tools/`, tested from `tests/`, a thin script in the skill. Reason: `pyrefly`
   `project-includes` and coverage `source` cover `packages/` only, so code under `skills/` would
   sit outside the type gate.
6. **Every rule carries its reason and its evidence.** One-pass findings are marked provisional in
   the file itself. Numbers are quoted from sources, never re-estimated.
7. **Delegate, then check the effect.** Wiring → `make bootstrap`; backlog use → `beads` skill;
   changes → openspec skills; reuse → `docs/agent-loop.md`; testing tools → shelf `bdd-tags`,
   `mcp-steps`, `json-match` and the `testing` modules. Blueprint states what must be true and how
   to check it.
8. **Stack-neutral core, stack packs on demand.** `stacks/python-uv.md` with evidence;
   `stacks/dotnet.md` from lifesim, labelled provisional inside the file; any other stack is
   written when its first project arrives (resolution 0014's own trigger logic).
9. **Ask the owner only what is his** — taste, scope, priority, risk appetite, money, anything that
   leaves the machine. One question format: numbered, context first, a recommendation that "yes"
   accepts. An agent's choice is recorded as the agent's. Nothing is recorded as his that he did
   not say (lifesim #33–37).
10. **Two vocabularies, for two different objects, with no shared word.** A *checkpoint* gets a
    verdict (principle 3: not set up · failing · passing · not applicable). A *piece of work* — a
    bead, a spike, a build step — gets a status that cannot read as done: untested · blocked on
    owner · broken · deferred (with the trigger that brings it back).
11. **Tests first.** `evals/` are written before SKILL.md, as the repo's convention requires for
    code. A checkpoint with no eval case covering it is a candidate, not active.
12. **The skill decays.** Every checkpoint has an expiry; RECONCILE re-justifies or deletes it.
    The anti-pattern list grows from real runs, each entry naming what fixed it.
13. **Where a check belongs, taken from agent-harness:** objectively broken → the repo's own
    `make check`; arguable → blueprint's audit; needs intent → the agent's judgment, asked as a
    question. Each checkpoint names which. The audit's goal is to shrink: every check that can
    move into the repo's gate moves there, so the repo enforces itself without blueprint.
14. **Prescribe config, never wrap tools.** agent-harness wrapped ruff, ty, hadolint and others in
    its own CLI and stalled when those tools changed their flags (its own design doc says so).
    Blueprint states what the repo's config and Makefile must contain; the tools run as themselves.
15. **Every checkpoint carries its fix, and the agent applies it.** agent-weiss stalled because
    its two file-writing actions raise `NotImplementedError` after 4 plans; every proposal became
    "do it by hand". A finding with no applied fix is "failing", not done.

## Structure — five layers, each answering one question

Owner request, 2026-10-10: define the points of view a tech stack is made of, find the answer for
every one, and give the skill more structure in how it works, shapes and demands.

| layer | question it answers | example | file |
|---|---|---|---|
| 1. phase | when | decide → spike → skeleton → thin thread → features | `SKILL.md` |
| 2. pillar | from which point of view | "type checking", "behaviour tests", "decision records" | `pillars/<pillar>.md` |
| 3. checkpoint | what must be true | `strict.types`: the type checker runs at its strictest preset in the gate | `checkpoints/<area>/<id>.md` |
| 4. stack answer | how, in this stack | python-uv: pyrefly `preset = "strict"`, `make typecheck` | `stacks/<stack>.md`, one row per pillar |
| 5. evidence | why we believe it | a2kay: 39 of 71 bugs workflow-shaped, 1 found by a unit test | cited in the checkpoint |

Rules that follow:
- **A stack pack is complete only when it answers every pillar** — a tool, or "not applicable"
  with the reason. A pillar left empty is a stack pack that is "not set up", the same verdict a repo
  gets. This is what makes a new stack cheap to add and impossible to add half-way.
- **Each pillar answer has the same fields:** tool and pinned version · where it is configured ·
  the strictest settings and why · the Make target that runs it · how it was seen failing once ·
  alternatives refused, with reason · evidence (track record, user reports incl. complaints —
  lifesim's five tests).
- **Checkpoints are stack-neutral;** a checkpoint names its pillar and reads the stack answer for
  the "how". So one checklist serves every stack.
- **Demands are explicit:** each checkpoint names the artifact or command output it demands as
  proof (the `verify` field), never "looks fine".

### Pillars a stack is composed of (draft, to put to Fable round A)

| # | pillar | python-uv answer (from the shelf) |
|---|---|---|
| 1 | runtime and version pin | Python ≥3.12, `.python-version` / `requires-python` |
| 2 | dependencies and lockfile | uv, `uv.lock`, upper bounds (RG004) |
| 3 | task runner and the gate word | make, `make check` |
| 4 | formatter | ruff format |
| 5 | linter, strictest preset | ruff, shelf preset, `make preset` drift gate |
| 6 | types / compiler strictness | pyrefly strict |
| 7 | architecture enforcement | pytest fitness tests (resolution 0005); layer DAG not ported yet |
| 8 | test runner | pytest |
| 9 | behaviour tests (Gherkin) and their driver | pytest-bdd <9, shelf `bdd-tags`, `mcp-steps`, `json-match` |
| 10 | test isolation and doubles | autouse hermetic conftest; shelf `testing` modules |
| 11 | coverage, following child processes | pytest-cov, branch, floor; subprocess coverage |
| 12 | mutation testing | mutmut + a2kay runner (promotion pending, shelf-8co) |
| 13 | property tests | Hypothesis (shelf runbook) |
| 14 | dependency hygiene | deptry |
| 15 | spelling and docs lint | codespell |
| 16 | security scans: secrets, dependency vulnerabilities | gitleaks, osv-scanner (not yet in the shelf) |
| 17 | hooks | shelf hook installer, one manager |
| 18 | container for the gate | not yet in the shelf (a2kay `test.Dockerfile` pattern) |
| 19 | CI | GitHub Actions, one reusable workflow running `make check` |
| 20 | packaging, release, install | git tags; `uv tool install` |
| 21 | config and secrets loading | shelf `settings-base` |
| 22 | errors | shelf `a2effect` |
| 23 | logs and traces | structured logs, OpenTelemetry (a2mcp pattern) |
| 24 | entry surfaces and their in-process test driver | CLI, MCP (fastmcp in-memory client), HTTP |
| 25 | shelf consumption | git + tag sources, `make guard` |

Non-stack pillars (shape, naming, backlog, decisions, agent instructions, working agreement) have no
stack answer; their checkpoints carry the "how" themselves.

## Fable round A — outcome (2026-10-10)

Full answer: [research/fable-round-a.md](research/fable-round-a.md). Verdict per point, the
authoring session's (✅ adopted / ❌ rejected):

| # | Fable's point | verdict | what changes here |
|---|---|---|---|
| 1 | The build order repeats agent-weiss's death: inventory, consults and fixtures before one checkpoint runs | ✅ | v0.1 = the gate pillar end to end on a2peer, lifesim and the shelf itself. A checkpoint earns its file by running; earns `active` by failing once with the fix applied (that failure is its regression row and its eval case). Everything else stays an inventory row. Supersedes the build order below |
| 2 | Principle 5's reason is false: `tools/` is outside pyrefly and coverage too, onboard-consumer included | ✅ (my error) | bead to extend the gate to `tools/` before blueprint scripts land |
| 3 | F1 is already decided by principle 3: overrides with reason codes checked into the repo *are* a state file | ✅ | `blueprint.toml` in the target repo: overrides (code, text, expiry) + the checkpoint-set hash it was audited against; generated per-pillar reports; beads for the work. Supersedes F1's lean |
| 4 | Plugin version ≠ skill version: `plugin.json` says `skills 0.1.0` for every shelf skill; `claude plugin tag` would make `skills--v0.1.0` | ✅ | consumers record the checkpoint-set hash, not a version; re-audit = set diff. F11 becomes a shelf-wide question |
| 5 | Plugin eval's sandbox has no network for toolchains, so `make check` cannot run on a python fixture | ✅ | two lanes: plugin-eval with stub-toolchain fixtures tests the audit logic; the real corpus is audited by hand with the real toolchain |
| 6 | A full audit exceeds `max_turns` 200 and one context | ✅ | `/blueprint <pillar>` scope argument; per-pillar eval cases; one report file per pillar (also conflict-free for parallel fan-out) |
| 7 | Three taxonomies (5 phases, 25 pillars, 13 areas) with no mapping | ✅ | area collapses into pillar; phase is a checkpoint field; tree = `checkpoints/<pillar>/<id>.md` |
| Q1 | Fixed 8-step run protocol: orient → enumerate (script) → check → validate (script) → report → fix → re-check → record; an empty repo runs the decide-phase owner round first | ✅ | becomes the body of SKILL.md |
| Q2 | Projected per-pillar runbook carries only check · verify · fix; why and evidence stay out of the load path | ✅ | refines principle 2 / F9 |
| Q4 | Day-one scripts under `tools/blueprint/`: enumerate, validate (refuses `passing` without evidence, `not checked` without reason, an expired override), project; diff soon after. Checks themselves never scripted | ✅ | supersedes principle 5's "no scripts in v0.1"; principle 14 stands |
| Q5 | User-invoked v0.1; amend resolution 0014 by one line (Kind: skill = plugin-distributed; invocation mode per skill) | ✅ | decides F6 |
| Q6 | Paired fault/clean cases from observed failures; regex over the report + tool_used/tool_order; ≤1 llm grader; `--ablation none` runs=1 while iterating, two arms runs=3 before a tag; static checks in `make check` | ✅ | decides F10 |
| Q7 | Evolution loop: reason codes and "blueprint lacks" lines captured per run → `tools/blueprint/mine.py` over consumers' `blueprint.toml` files and transcripts (candidates only) → regressions table → RECONCILE adopts or rejects, a rejection written into the checkpoint's Refused section → the set-hash diff tells each consumer which checkpoints to re-audit; a session hook logs, never blocks | ✅ | the reabsorption loop the owner asked for |
| 9 | Not thought about: the shelf must pass its own blueprint (5 known defects); ~40 judge questions on an empty repo need one owner round per phase; multi-stack repos need `applies_to` as path globs; report evidence can leak PII; the plugin ships the whole repo | ✅ all | added to risks; PII needles run in the validator |

## Open forks — need research or Fable before deciding

| # | fork | options | my lean | settled by |
|---|---|---|---|---|
| F1 | where audit state lives | (a) beads only: each failing checkpoint becomes a bead labelled `blueprint`, plus a generated report file; (b) a checked-in `blueprint.yaml` with per-checkpoint status (lifesim #32) | (a) — one job per system; beads already survives context loss. Against it (R4): Copier, cruft and projen all keep a version pointer in the repo, and cruft records a rejected template change as a commit; beads-only has no record of which blueprint version a repo was last audited against | Fable |
| F2 | report shape | the per-candidate verdict tree from k-my `micro-software` vs a new shape | reuse if it fits | R6 + read micro-software |
| F3 | restart vs migrate for an existing repo | rule for when the audit recommends a fresh skeleton | R6 has two owner rulings for restart ("remove the whole thing … except linters"; "shape of the code doesn't matter"); both keep the gate and the behaviour tests and throw away the code. Lean: a restart keeps the gate + behaviour scenarios as the spec and rebuilds code behind them; migrate when the scenarios do not exist yet (write them first: a2kay order use cases → isolation → prune → merge → shelf) | Fable |
| F4 | which a2kay testing lessons are universal and which are Python-shaped | — | Gherkin-first, placement table, hermetic env, mutation-proven deletion are universal; tool names are not | Fable + R5 |
| F5 | scoring | binary per checkpoint vs maturity tiers | — | **decided**: principle 3 (set up? / working? per checkpoint); no tiers, no averages (agent-weiss's domain averages hid the inverted scores) |
| F6 | trigger: auto vs user-invoked | R8: ship v0.1 user-invoked (`disable-model-invocation: true`), triggered by a line in each consumer's AGENTS.md (and by `make bootstrap`), zero always-on cost; k-my skills already cost ~4,326 tokens every session and rarely used skills lose their description first when the listing budget overflows. Against: resolution 0014 scopes `Kind: skill` to push-based skills; a user-invoked one may only be evaled through a prompt starting `/blueprint` (untested) | user-invoked for v0.1 | Fable A |
| F9 | loading unit vs authoring unit (R8) | author one file per checkpoint; ship a generated `references/<area>.md` per area + an index in SKILL.md, because docs require references one level deep and nested files get read partly | take R8's version | Fable A |
| F10 | audit output an eval can grade (R8) | plugin eval has no code graders (regex, tool_used, tool_order, file_exists, llm, baseline); so the audit writes a report file, one line per checkpoint `id · set up? · working? · evidence`, graded by regex; each fault fixture paired with a clean fixture so "everything failing" cannot score | take | Fable A |
| F11 | tag naming (R8, untested) | `claude plugin tag` makes `<name>--v<version>`; shelf rule is `<name>-vX.Y.Z` | check before the first tag; amend the skill-kind spec if the CLI cannot change | test it |
| F7 | decision records while a2kay repo vaults are unbuilt | ADR 0046 (a2kay) designs repo vaults with kernel kinds (decision, option, research, probe, question, source, claim, signal, artifact; `status: superseded` + `superseded_by`; a probe links the claim it tests and states expected outcomes before it runs). The engine is open beads under `a2kay-fmj1`: repo storage mode, serverless `a2kay validate`, slug ids. No repo has a vault today | prescribe the kernel file shape now, gate it with a frontmatter check until `a2kay validate` ships, then swap; leave existing `docs/adr/NNNN-` folders alone, slugs only in new vaults | Fable + a2kay owner priority |
| F8 | the six points where the a2peer and lifesim kickoffs disagree | CLAUDE.md↔AGENTS.md symlink direction; requirements in openspec vs inside system docs; how a spike is recorded; decision format; CI or none; session-end hook | AGENTS.md canonical + CLAUDE.md symlink (shelf's own rule); openspec for requirements; spike = probe file + bead; kernel decision fields; CI always (a "no CI" decision is a recorded n/a, not a default); beads session hooks on | decide as agent, list in the owner round |

## Research plan — each item names the decision it settles

| id | research | settles | state |
|---|---|---|---|
| R1 | a2kay testing sources → `references/testing.md` draft with cited numbers | testing area content; F3, F4; which a2kay scripts to promote | done — promote `container_slot.py` (host tool, not into `process-lock`), `lineage/metrics.py` + `check.py`; `prune/run.py` only once its a2kay paths are parameters; `lineage/build.py` later |
| R2 | agent-weiss / agent-harness | checkpoints we would miss; formats; why it stalled | done — adds a security group (.env ignored, gitleaks, osv-scanner, ignore lists with expiry), hooks installed not just configured, agent-readable tool output settings, CI actions pinned to SHAs with `permissions:`, AGENTS.md content audit, Dockerfile/compose rules; reusable Makefile/CI/Dockerfile templates |
| R3 | a2kay vault kinds; a2peer, lifesim as built; Makefile/CI/Docker conventions across repos | knowledge area; gate area; real gaps for the eval corpus | done — see F7, F8; a2web's reusable `gate.yml` (one workflow running `make check`, on push and on release tags) is the CI model; a2kay's CI has drifted to a subset of `make check` |
| R4 | external: how others encode repo standards | checkpoint format; template vs audit split | done (one pass): [research/repo-standards.md](research/repo-standards.md) — adds the not-checked verdict, reason codes, `lifecycle` and `effort` fields; confirms binary-per-checkpoint (Factory passes a level at 80%, agentready scores 72.5/100: both pass with failures inside); AGENTS.md checked for content (generated context files measured at about −3% success, +20% cost — secondary source); ❌ Copier-style three-way merge, ❌ any rule engine (repolinter archived 2026-02-06) |
| R5 | per-stack enforcement tools: architecture (import-linter vs tach, ArchUnitNET, dependency-cruiser), strictest presets, Gherkin runners (pytest-bdd, Reqnroll, cucumber-js), mutation tools | stack packs; F4 | to run, scoped to python-uv + dotnet now |
| R6 | the owner's corrections during past repo setups (3,299 owner messages across 13 repos, streamed by script; the search tool returned one snippet per session) | anti-patterns list; missing checkpoints; F3 | done (one pass): [research/owner-corrections.md](research/owner-corrections.md) — 21 new checkpoints into `inventory.md` §13; strongest repeat: the local gate weaker than CI (a CI job red for 9.5 days unseen) |
| R7 | `claude plugin eval` / `details` / `tag` mechanics | eval design | done: [research/plugin-tooling.md](research/plugin-tooling.md). A case = `evals/<case>/prompt.md` + `graders/`; each run starts in an empty workspace, so a fixture repo is a `scaffold_script` (runs with `--scaffold`); graders: regex, tool_used, file_exists (free), llm, baseline; two arms by default; CI form `--json --threshold --max-cost-usd`. Description ≤1,024 chars for portability. Needs Claude Code ≥ 2.1.269 per docs (this machine: 2.1.259) |
| R8 | best practices for building skills (owner request, 2026-10-10) — done (one pass): [research/skill-practices.md](research/skill-practices.md); findings in F6, F9–F11 and below |

Cross-check rule: any claim a design decision rests on gets a second, independent pass before it
drives the decision.

## Fable consults

Run as two briefed rounds once the research lands, plus a red team on the draft. Each round gets
the files, not a summary.

- **Round A — the skill as software:** checkpoint-per-file + generated index vs alternatives;
  scripts or none in v0.1; state (F1); evals for a judgment-heavy audit; always-on cost; how
  blueprint evolves and reabsorbs lessons from the projects that run it.
- **Round B — the content:** the questions below (F3, F4, scope, F7, F8).
- **Round C — red team** on the first draft against a fixture repo.

Questions, one each, with my recommendation:

1. **State (F1):** beads-only plus a generated report, or a checked-in state file? Rec: beads-only.
2. **Universal vs Python-shaped (F4):** which a2kay testing rules hold for a .NET game, a TS web
   app, a CLI? Rec: the list in F4.
3. **Restart vs migrate (F3):** what observable signals mean "new skeleton, port the behaviour"
   rather than "migrate in place"? Rec: none yet; ask open.
4. **Scope:** is anything in the checklist actually agent practice rather than repo content, or the
   reverse? Rec: the split in the proposal.
5. **Red team (after the draft):** run the draft against a fixture repo; what would an agent still
   skip, fake, or mark ✅ without proof?

Each consult gets the relevant files, not a summary; the answer is recorded with a verdict per
sub-claim.

## Build order

0. **One checkpoint end to end first** (the thin thread, lifesim #30, and the opposite of how
   agent-weiss died: machinery, spec and distribution before one working check). Pick the gate
   checkpoint (`make check` exists and fails on a planted violation): checkpoint file, a pass
   fixture, a fail fixture, an eval case, the agent applying the fix. Only then widen.
1. Research R1–R7 → one merged checkpoint inventory (dedupe the three sources plus prior art;
   keep the source of each item: owner / agent / Fable / a2kay / prior art).
2. Fable 1–4 on the inventory and principles. Then one owner round with only his questions.
3. Evals first: fixture repos — empty; half-set python-uv; a legacy repo with known faults. Then
   the real corpus, audited read-only: a2peer, lifesim, a2kay, a2web, a2db. Their known problems
   are the expected findings.
4. Write `SKILL.md` (phases, how to audit, verdicts, resume rule, not-done words) + checkpoint
   files + `references/` (testing, knowledge, shelf, gate) + `stacks/python-uv.md`.
5. Run evals with and without the skill (skill-creator loop); owner reviews in the viewer.
6. Fable 5 red team. Fix. Description optimisation against the near-misses.
7. `claude plugin details` → measured always-on cost into `catalog/blueprint.toml`; population
   floor in `tests/test_gate_covers_every_skill.py`; `make check` green. Tag only on approval.

## Risks / Trade-offs

- **The checklist grows until nobody runs it whole.** → Per-file checkpoints with expiry; the
  agent opens only the areas and stack in play; RECONCILE deletes.
- **Checkbox theater: ✅ without proof.** → Principle 4; red-team consult; evals plant faults.
- **Doctrine from one project (a2kay) generalised too early.** → Fable 2; each rule keeps its
  source; stack-specific parts go to stack packs.
- **The shelf's own onboarding has gaps blueprint would inherit.** The machinery map found:
  `linter-preset` copies `check` but not the `preset` target it depends on, nor `[tool.pyrefly]`
  or pytest config; `onboard.py` says it checks `../shelf` and does not. → shelf-4mz, shelf-4f2 (plus shelf-zox, shelf-dzl, shelf-0h1), fixed before
  blueprint relies on them.

## Open Questions (owner)

Decided by the owner, 2026-10-10 ("yes to both"): `dotnet` pack written now, labelled
provisional; v0.1 ships with the interim frontmatter gate for decision records instead of waiting
for a2kay repo vaults.

- If Fable splits on scope (consult 4): does agent practice for orchestrating many agents get its
  own skill?
