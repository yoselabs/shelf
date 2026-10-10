# Fable round B — the content of the checklist (2026-10-10)

Consult on `proposal.md`, `design.md` (incl. the later "Structure — five layers" section, question 7 in §8), `inventory.md`, the six research files, the constitution,
the doctrine and resolution 0005. Verdict vocabulary: **supported / refuted / untested**, per
sub-claim. ✅ do · ❌ refuse · ⚠️ do with the stated change. Tool facts not verified in this session
are marked untested, never asserted. Every number quoted is from the research files, not
re-estimated. Nothing here edits the inventory; contradictions in it are named, not fixed.

## 0. The finding that governs the rest

**The a2kay testing remedy is a prediction, not a measurement.** What is measured: 39 of 71 closed
bugs were workflow-shaped; a test found 1 of 71 (a flaky one); 2 of 13 journeys had a client-level
test (a2kay-testing §0). What is *not* measured: that a use-case layer catches those bugs. TS §2's
"24 yes / 14 maybe / 1 no" is an agent's judgement of what a scenario *would* have caught, written
after the fact. The scenario inventory did find 8 bugs while being written (TS §10) — that is
discovery, not regression protection.

Consequence for blueprint: the testing area (§9 of the inventory, 19 checkpoints) is downstream of
one hypothesis. Carry it, but mark every testing checkpoint whose *why* cites TS §2 as
**supported by prediction**, and name what confirms it: classify a2kay's next 30 closed bugs by
"which test turned red first" (scenario / unit / none). If scenarios catch fewer than, say, a third
of workflow bugs, the doctrine is wrong and blueprint ships it to every new repo. No other claim in
the inventory carries this much weight on this little evidence.

## 1. Universal vs Python-shaped (F4)

**Verdict on the F4 lean ("Gherkin-first, placement table, hermetic env, mutation-proven deletion
are universal; tool names are not"): ⚠️ supported with one substitution — the universal thing is
not Gherkin.**

### 1.1 What the evidence actually supports as universal

| invariant | evidence | holds for .NET game / TS web / Go CLI / infra? |
|---|---|---|
| Behaviour tested at the **actor's real surface, in process**, before code | 168 CLI calls: ~7.6 min as subprocesses vs ~37 s in process (PREP §2); a2kay bugs recurred at sibling paths tested "at the lowest convenient level" (TS §2.1, §3) | yes / yes / yes / **no actor** (see 1.3) |
| A **controlled vocabulary with a checker** | 4 parallel writers: 201 phrases for 212 scenarios → 68 after one merge; "the step library does not prevent sprawl by itself. A fixed vocabulary file and a checker do" (TS §10) | yes — the carrier differs |
| **Placement table**; extend before create; never name a file after a change | 67% of feat commits added a test file; 24 files named after a change; 27 never edited again (TS §4.3) | yes, all four |
| **Hermetic by default**: tmp HOME, app env scrubbed, no network, no real OS services, fake model unless marked | `profile_regen` called the real `claude` CLI; the first owner scenario wrote the real `~/.config` (DES §3) | yes, all four; the *mechanism* is per stack |
| **Fake below your own policy** (process boundary), not at the port | bug `oub` lived in `_screen`, before git; a port fake skips it (PREP §13) | yes; this is a design rule, not a tool |
| **Every hermetic test in the gate; no nightly** | "a break would surface a day after the commit" (DES §3a-revised); owner row 25 | yes, with the lane rule in §4 below |
| Unit tests as **tables**, pairwise not product | 720 → 20 rows kept 1,869 of 1,888 kills (LEDGER i0) | yes; every xUnit has parametrize / `[TestCase]` / `test.each` / table tests |
| **Delete only with mutation evidence** | coverage left 85% undecided; mutation kept 4 of 61 (PM §4) | method yes; tooling: Stryker.NET / StrykerJS exist (untested here), Go mutation tooling is weak (untested) — make it a pack capability, not a universal checkpoint |
| **Traceability tags** `@spec:` / `@bug:`; strict-xfail for known bugs | typo cannot become a permanent skip (ADR 0044) | tags yes; strict-xfail is a pytest/bdd-tags feature — other runners need an equivalent or the rule drops to "a known bug is a bead + a skipped test naming it" |
| A bug found while writing a test is filed at once | 8 bugs found writing the inventory (TS §10) | yes; it is conduct, though — see §3 |

### 1.2 What is Python- or a2kay-shaped (stays in `stacks/python-uv.md` or is dropped)

- pytest-bdd mechanics: `scenarios()` collectors, autouse conftest ordering, duplicate-name silent drop,
  the `<9` pin, xdist worker start cost (3.5 s), `-n0` under 25 scenarios, `PYTHONDONTWRITEBYTECODE`.
- The lineage ranking and prune pipeline: pure Python AST + mutmut + coverage contexts; on spike branches
  only; 3–6 h per tree. ❌ as a universal checkpoint (`test.lineage`, `test.helper-smells`). ✅ as a
  python-uv pack *reconcile tool* run on demand. The helper-smell taxonomy (55% of helpers are symptoms,
  SO §1.1) is a useful reading guide; it is not a check.
- `gate.container` 6×: caused by macOS endpoint security + Defender (~815 cpu-s of a run, PREP §4;
  25 ms vs 1 ms process start, PREP §9). Not a property of Python, not a property of containers. See §5.
- `arch.domains` (noun folders chosen by first `@spec:` tag, verbs in file names): one repo's measured
  choice (7 domains 52% edges inside, ADR 0045). Generalise only as "test folders = a fixed noun set
  declared in one README"; mark provisional.
- Real-git lane, `RecordingHistory`, the history invariant: a2kay's own.

### 1.3 Gherkin-first: where it fails and what replaces it

**Gherkin's main selling point — a stakeholder can read it — is worth zero here.** The owner is solo;
the readers are agents. What remains of Gherkin's value is (a) a forced controlled vocabulary, (b) a
file per actor goal, (c) tags. Any carrier that preserves (a)–(c) counts. The owner's own repos
already refute "Gherkin everywhere":

- The shelf pilot rewrote mcp-bridge and git-porcelain as features and both grew 50–90% in lines
  (AGENTS.md conventions; a2kay-testing §9). Rule already in force: Gherkin only where steps are shared.
- lifesim tests a simulation with `tests/scenarios/*.yaml` (design sentence + seed + expectations),
  golden logs, and property tests (knowledge-and-kickoffs §b). A sim has no step list; its "actor goal"
  is a statistical property over ticks.

| repo kind | behaviour-first carrier | what it must preserve to count | verdict |
|---|---|---|---|
| Python MCP server / CLI / service | pytest-bdd with shared steps (`mcp-steps`, `json-match`, `bdd-tags`) | STEPS.md + checker; in-process client | ✅ supported (a2kay) |
| Python package with its own logic | plain pytest, one file per module | placement table | ✅ supported (shelf pilot) |
| .NET simulation / game | scenario files (seed + expectations) + golden logs + property tests; architecture tests | determinism (`test.determinism`), a scenario vocabulary in one schema file | ✅ supported (lifesim as built); Reqnroll only if an actor performs steps — untested |
| TS web app | Playwright specs with a fixtures module as the only allowed API; component tests for logic without the browser | a lint rule that tests import only from `fixtures/` (the STEPS.md equivalent); tags via annotations | untested — cucumber-js adds a layer nobody reads |
| Go CLI | `testscript` (txtar command scripts) — the Go-native "feature file" | commands = the vocabulary; in-process `main` via `testscript`'s `TestMain` hook | untested in this session; the shape matches |
| Infra repo (homelab, Nix/Komodo) | no actor. Plan-diff tests, policy tests over the rendered config, one ephemeral apply as smoke | "declared ⇔ live" check (`ops.declarative-infra`) | ✅ Gherkin refuted here; note resolution 0005's OPA ban does not reach infra repos where the policy engine is the stack |

**Recommendation.** Rename `test.usecases-first` to *actor-surface scenarios first*; its `check`
names the three preserved properties, its `applies to` names the carrier per pack. Gherkin becomes the
python-uv pack's default carrier, not a universal rule. `test.steps-vocab` generalises to "the
vocabulary lives in one file and a check rejects phrases outside it"; for non-Gherkin carriers the
check is an import/lint rule.

### 1.4 Two universal items hiding in the Python speed table

- **Startup-time budget for CLIs and servers**: eager import cost 2.6 s per subprocess (PREP §2); the
  gate's affordability depended on fixing it. A test asserting a startup ceiling is cheap and universal
  for CLI/MCP packs. Missing from the inventory.
- **Parallel-safe suite**: "Scenarios that must run serially: 0" (PREP §2) was the enabling fact for
  all-cores runs. Missing from the inventory as a checkpoint; `test.hermetic`'s verify should include
  "the suite passes with N workers".

## 2. Restart vs migrate (F3)

**Verdict on the lean ("keep gate + behaviour scenarios, rebuild code; migrate when the scenarios
do not exist yet — write them first"): ⚠️ supported, with three corrections.**

1. **The two rulings came from pre-user repos** (reco, budget — owner-corrections "Evidence for F3").
   Neither had persisted data, migrations, or an external consumer. The inventory has nothing on
   stored formats, migrations, API compatibility. Those are the only things that make a restart
   *unsafe*, and they are absent because every source project is pre-production. Add them to the
   signal table below and to the inventory (§5.1).
2. **"Keep the scenarios" assumes the scenarios are complete.** a2kay's own measure: 2 of 13 journeys
   covered before the inventory; the inventory itself found 8 bugs. So F3 collapses to one
   measurement: **journey coverage** — fraction of actor goals with a green scenario at the real
   surface. Below a threshold, the only legal move is *write scenarios against live behaviour*
   (this is what the owner's `k-my:code-to-spec` skill does: harvest rules, quirks, magic numbers
   before a rebuild). Restart is never recommended by the audit; the audit outputs the signals and
   the owner decides (money, time, risk — principle 9).
3. **Restart is a strangler, not a delete.** Doctrine idea 1: the contract is the gene, code is the
   phenotype. The safe form is: scenarios green against the old code → new skeleton beside it →
   the same scenarios green against the new → old deleted. a2kay already found the failure of two
   backends behind one surface drifting (DES §3a); running one suite against both is the guard.

### 2.1 Signals an audit can observe

| signal | favours | how observed |
|---|---|---|
| Journey coverage < ~half of actor goals | neither yet — write scenarios first | count goals in the spec / vault vs `.feature` (or carrier) files |
| Entry point cannot be driven in process (script with module-level side effects, globals, `sys.exit` in the middle) | restart | try the in-process client; `test.usecases-first` verify fails for structural reasons |
| Layer DAG has cycles across would-be layers; `arch.enforced` cannot be declared without allowlisting most edges | restart | run the arch tool with the intended DAG; count violations vs modules |
| Strict gate at the shelf preset yields errors in most files | restart, if small; migrate with a dated suppression file, if large (see §6.2) | run the preset, count files touched |
| Persisted data, migrations, saved formats exist | migrate, or restart only with golden-file compatibility tests (`test.goldens`) in the kept suite | grep for schema / migration dirs / save formats |
| External consumers (published package, API clients, MCP clients the owner uses daily) | migrate | tags on registries, `ops.dogfood` state |
| Scenario count stable across the last N sessions and all green | restart is now *possible* | git log of the scenario dir |
| Code volume small relative to scenario volume | restart is *cheap* | LOC ratio; a hint, not a rule |
| Owner says the code is disposable | restart allowed | recorded as an owner decision in the vault |

Order: safety → gate exists → scenarios → *then* the F3 decision. Never before scenarios.

## 3. Scope

**Verdict on "the split in the proposal" (agent practice out, repo content in): ⚠️ the line is
right; the inventory does not honour it.**

### 3.1 Conduct dressed as repo content

These are verified by grepping prose in AGENTS.md — the existence check C3 refuses, moved from
files to sentences:

`ws.commit-policy`, `agents.question-format`, `agents.ask-only-owners`, `agents.no-fake-answers`,
`agents.escalation`, `agents.worktrees`, `agents.phases`, `agents.dod-per-bead`, `gate.ci-down-loud`,
`gate.whole-repo` (as text), `kb.parked`, `kb.bug-on-sight`, `shape.second-opinion`,
`shape.spike-trigger`, `shelf.promote`, `shelf.seam` (the judge half), `ops.dogfood`,
`arch.patterns-early`, `arch.one-process`, `stack.five-tests`, `ws.location`.

That is 21 of ~181. A sentence in AGENTS.md does not make an agent ask numbered questions; the ETH
measurement (generated context files −3% success, +20% cost, secondary source) says prose is cost,
not control. Where conduct *can* be enforced it is a hook or a gate, not a sentence
(Claude Code docs: "hooks are deterministic", CLAUDE.md "advisory").

### 3.2 Kickoff steps dressed as checkpoints

`shape.*` (16 items), `name.*` (4), `stack.decision`, `ws.visibility`, `ws.merge-policy` are done
once, in order, with the owner in the loop. They produce vault entries. A checkpoint re-audits
state; these are a workflow. Principle 1 ("one mode") and Q6 (ordering) contradict each other, and
Q6 wins: an ordered kickoff is a runbook, not an audit.

### 3.3 The cut

| part | what it holds | cadence | count after the cut |
|---|---|---|---|
| **audit** (the skill's core) | repo state verifiable by a command; packs | every run, idempotent | ~60 after dedupe (§5.2), ~15 in v0.1 |
| **kickoff runbook** (a phase doc inside the same skill) | shape → name → stack → spikes; each step's *output* is a vault file the audit later checks exists and is complete (`kb.decision-complete`, probe outcomes pre-registered) | once per repo | ~25 steps |
| **conduct** (not blueprint) | question format, escalation, worktrees, commit policy, bug-on-sight, promote triggers | standing, every session | 21 → the shelf's resolver block / `docs/agent-loop.md` / the owner's global instructions |

Keep audit and runbook in one skill folder (shared checkpoint files, one trigger). The audit never
re-asks a kickoff question; it checks the kickoff's artefacts. Conduct exits blueprint entirely:
blueprint's only conduct check is "the resolver block is present and current" — delegated to
`onboard-consumer` already.

Is the skill trying to be too much? Yes, in the agent-weiss way: 181 controls, none applied, is the
failure both prior-art repos died of. The build order's step 0 (one checkpoint end to end) is the
right antidote; the inventory should be sized to it.

## 4. Conflicts C1–C8, F7, F8

| # | lean | verdict | reason / change |
|---|---|---|---|
| C1 pyrefly | ✅ supported | But the checkpoint must say "the shelf preset's type checker at its strict preset", never `pyrefly`. A tool name in a rule is the instance data `agents.no-instance-data` bans; the preset switched once already (ty → pyrefly, 2026-09-12) |
| C2 import-linter/tach vs native pytest | ❌ false conflict | Resolution 0005 rejected OPA as a **non-hermetic binary** and chose native tests for **AST-fact rules** (dup bodies, name collisions). An import DAG checked by an in-toolchain dependency (import-linter, tach, ArchUnitNET, dependency-cruiser) violates nothing in it. Hand-writing a DAG checker in pytest is the tool-wrapper trap in reverse. **Real finding:** a2kay uses import-linter, a2web uses tach + `tests/architecture` — the python-uv preset must pick one (bead). Universal form = `arch.reads-design`: the tool reads the one declared DAG (lifesim's ArchUnitNET reads `depends_on` from `design/systems/*.md`) |
| C3 content, not existence | ✅ supported | Go further: README purpose line, SECURITY contact, LICENSE apply only to **public** repos (`applies to: visibility=public`). A SECURITY.md in a private solo tool is cargo cult |
| C4 AGENTS.md canonical, CLAUDE.md symlink | ⚠️ canonical yes; symlink mechanism no | The checkpoint is "one canonical file; every client entry file resolves to it with zero duplicated lines". The mechanism is a pack choice: symlink on POSIX, a one-line `@AGENTS.md` import (a2web's form) where symlinks are unreliable. lifesim is .NET/Godot; a Windows checkout breaks a symlink unless `core.symlinks` and developer mode are on (untested here, but the risk is well known). See §7.1 |
| C5 state file vs beads | Round A, but content forces one line | Principle 3 already requires overrides **checked into the repo** with reason codes. Beads-only contradicts principle 3 on its own terms. Minimum: a small checked-in file with `blueprint_version` + overrides; findings go to beads. R4 row 12 (Copier, cruft, projen all keep a version pointer) points the same way |
| C6 lefthook vs shelf native installer | ⚠️ the invariant is universal, the manager is a pack choice | `gate.one-hook-manager` is the rule: one owner, bd's `core.hooksPath` chained, proven by one real commit. The shelf installer is Python; a .NET repo has no reason to run it. Its "refuse foreign managers but name where to add" is right for python-uv consumers and wrong as a universal rule |
| C7 `just` vs `make` | ✅ supported, per pack | Mandate the **target names** (`bootstrap check lint fix test`, the five-repo intersection) and "one runner per repo, hooks and CI call it" — not the runner. `make` on Windows is friction; `just` is fine for .NET |
| C8 CI by default; "no CI" = recorded n/a | ✅ supported | Add: the n/a needs a **revisit trigger** (a second machine, a collaborator, a public push). Without CI the only proof that the gate is reproducible from a clean clone is a manual `make bootstrap` on a fresh checkout — make that the n/a's compensating check |
| F7 kernel shape now, frontmatter gate until `a2kay validate` | ⚠️ supported with two changes | (1) **Pin the kernel pack version** in the frontmatter check (`pack: kernel@<a2kay commit>`) so the later swap is a diff, not a surprise — fmj1 is open and ADR 0046 may move. (2) lifesim's 247 decisions carry `about`, `derived_from`, `supersedes`; the gate fails all 247 on day one. The fix must be "declare them as overlay fields in `.a2kay/ontology/`" (ADR 0042 §2 allows this), not deletion. v0.1 kinds: **decision, option, probe** only; claim / signal / source are research ontology and cargo cult for a software repo until a project needs them. Slugs for new vaults, old `NNNN-` dirs untouched: ✅ |
| F8 symlink | see C4 | |
| F8 openspec for requirements | ⚠️ supported for software; one home per repo, declared | lifesim's product-design pack puts requirements inline in `system` files by its own decided ontology; forcing openspec there creates the two-homes finding the rule exists to prevent. Rule: "requirements have exactly one home per repo, named in AGENTS.md; openspec is the default" |
| F8 spike = probe + bead | ✅ supported | The valuable bit is the **pre-registered outcome** (the kernel's only probe condition); neither kickoff had it |
| F8 kernel decision fields | ✅ with the F7 version pin | |
| F8 CI always | ✅ | as C8 |
| F8 session hooks on | ⚠️ client-specific | `.claude/settings.json` is a Claude Code fact inside a client-neutral AGENTS.md doctrine. Put it in a `client-claude` pack; bd's own hook install covers the start hook. The Stop-hook warning on in-progress beads (lifesim) is worth keeping there |

Contradictions inside the inventory that need a ruling, not a note:

| contradiction | ruling |
|---|---|
| `test.no-nightly` / `gate.no-test-outside` ("every test kind runs in `make check`") vs knowledge-and-kickoffs §c ("slow/real-env lanes stay out of `check`", a2web `test-browser`) vs `test.lanes` (vendor opt-in, out of the gate) | **Hermetic in; paid/vendor out.** A lane may leave `check` only if it needs money, a credential, or a resource not on every dev host — and then it runs in CI as a named workflow, checked by name after a push (`gate.local-covers-ci`). Slowness alone never justifies a second suite; the fix is in-process drivers and measured speed |
| Coverage: PM §2 "covering a line is not checking it; coverage decides nothing" vs prior-art floor 90–95 vs `test.coverage-gate` | A floor is a ratchet against test-free code, set at today's number and raised, never a target; **diff-coverage against main** is the agent-useful check (stops new uncovered code without a global fight). Drop "90–95" as a number; it has no evidence |
| `strict.proven-red` ("made to fail once") is unverifiable after the fact | Enforceable form: the repo's tests include a **planted-violation test per custom guard** (`fb:mutation-test-the-rules`: a rule green for months that could not fire). That is a gate check, not an audit memory |
| Principle 1 "one mode" vs Q6 ordering | §3.3: audit + runbook |

## 5. The inventory

### 5.1 Missing — what a world-class setup has that the inventory lacks

Ranked by value for this owner's repos (agent-built, mostly solo, Python/.NET, pre-production):

1. **Fresh clone → `make bootstrap` → `make check` green.** The single most valuable checkpoint;
   it is in prior-art (`make bootstrap`) and nowhere in the inventory as its own line
   (`shelf.onboarded` is the shelf wiring, not this). Verify: clone to a temp dir, run both, time it.
   This is also the compensating check for a no-CI repo (C8).
2. **Lockfile committed and the install is frozen** (`uv sync --frozen`, `packages.lock.json`,
   `pnpm-lock`). `stack.pins` covers bounds, not the lock as the install source. CI drift at a2kay
   (knowledge-and-kickoffs §c) is this.
3. **Toolchain version file** (`.python-version` — a2kay-testing §8: `uv` picked 3.13 in a fresh
   worktree and `lxml` failed; `global.json`; `.nvmrc`). Half of `stack.pins`; make it explicit.
4. **Flaky test = bug; retries banned in the gate.** A flaky test cost a2kay's prune ~100 + 43 min
   (LEDGER); `pytest-rerunfailures` and Playwright `retries` hide the class. Missing.
5. **Parallel-safe suite** (§1.4). Missing.
6. **Startup-time budget** for CLI / MCP packs (§1.4). Missing.
7. **Persisted data: migrations and format compatibility.** For anything with a store or a save
   file (a2kay vault, lifesim saves): forward-only versioned migrations applied to an empty store in
   the gate; golden files for every persisted format with a load-old-save test. `test.goldens` is a
   corner of this. Absent because all source projects are pre-production — the gap that makes F3
   unsafe (§2).
8. **README quickstart that runs.** The first actor scenario for a tool is "a stranger follows the
   README". Execute the README's commands in the gate (or a doc-test). `ws.hygiene-files` as content
   check is this, made verifiable.
9. **LLM-app pack**: prompts are files under test with golden outputs (prompt versioning = git);
   fake model in the gate (`test.hermetic` has it); an eval lane out of the gate with a cost cap and
   a trigger (a2web `eval`, a2kay cold-agent runs found 21 bugs — discovery, ADR 0044); record &
   replay for vendor APIs (PREP §13 ✅); tool descriptions tested with a real agent
   (`ops.agent-ergonomics`). Only the last two are present.
10. **Monorepo pack**: per-member gate (shelf's deptry per package), per-package tags, a generated
    index with an anti-tamper check (R4 verdict 10). Shelf and a2kay are monorepos; nothing in the
    inventory says so.
11. **Clock and randomness injectable** — generalise `test.determinism` from sims to any repo
    (a2kay's "clock seam" is still open, TASKS 2.11). Candidate.
12. **Backup / restore test** for apps with state. Candidate; no source project has one.
13. **Web pack**: accessibility (axe in the browser lane), bundle-size budget, CSP. Pack only.
14. **Dependency licence allow-list** — public / published repos only. Candidate.
15. **Blueprint drift signal** — a `cruft check` equivalent: the repo records the checkpoint-set
    version it was last audited against; a newer set is a finding. Without it repos go stale
    silently. (Round A mechanism; the content need is here.)

Skip as cargo cult for these repos: SBOM, devcontainer.json (the gate container covers
reproducibility where it is needed), SLO documents, branch-protection rules on a solo repo.

### 5.2 Wrong, duplicated, unenforceable, cargo cult

**Wrong**

- `gate.container` as a default. The 6× (340 s → 64 s) is macOS endpoint security + Defender
  (~815 cpu-s of a 1,281 cpu-s run; 25 ms vs 1 ms process start). On a Linux host or CI the gain is
  nil; Docker Desktop on Windows is slower. Checkpoint form: **gate wall time is measured and printed;
  a container is prescribed only when host overhead is measured above a stated ratio.** "Copy, never
  bind-mount" has the same root cause and belongs in the python-uv pack's container recipe, not a rule.
- `ws.pii-guard` as written **leaks**: a needle list of client, family and owner names, committed,
  publishes the names it exists to hide — in a public repo that is the original incident (owner row 23)
  re-created. Needles must live outside the repo (an env-provided file, a user-level config) or be
  hashed. This is a design gap in the shelf's guard, not a checkpoint; file it before the checkpoint
  ships. `arch.guard-needles` ("from the population") makes it harder, not easier.
- `strict.proven-red` — see §4; unverifiable after the fact.
- `test.coverage-gate` with a 90–95 number — see §4.
- `agents.canonical` demanding a symlink — see C4.

**Duplicated** (one checkpoint each, fold the rest)

| keep | fold in |
|---|---|
| `gate.no-test-outside` | `test.no-nightly` (the inventory says so itself) |
| `ws.secret-scan` | `ws.secrets-ignored` (gitleaks covers both tree and history) |
| `stack.pins` | `stack.upper-bounds`, plus the lock and toolchain file from §5.1 |
| `gate.one-hook-manager` | `gate.hooks-installed`, `kb.beads` (same `bootstrap-verify`), `shelf.onboarded` (delegate) |
| `kb.decision-complete` | `shape.decisions`, `shape.refused`, `kb.vault` (the decision half), `kb.supersede` — four checkpoints on one file |
| `shape.verdicts` | `shape.cross-check` |
| `arch.layers` + `arch.enforced` + `arch.reads-design` → one `arch.dag` | `arch.structure`, `arch.typed-seams` (= `strict.types`) |
| `test.usecases-first` | `test.first-feature`, `test.thin-thread` (the latter is a runbook step) |
| `gate.whole-repo` | `agents.dod-per-bead` |
| `strict.suppressions` | `ws.ignore-expiry`, `strict.banned-apis` (a suppression is a suppression) |
| `gate.local-covers-ci` | `gate.ci` (one workflow, same command) |

**Unenforceable as written** → runbook or conduct (§3), or candidate until a verify exists:
`shape.research`, `shape.spike-trigger`, `stack.five-tests`, `arch.patterns-early`, `arch.one-process`,
`kb.parked`, `kb.glossary` (judge), `name.plain` (owner taste: EN+RU+UK+TR+ES is his, not a rule),
`shape.value-claim`, `agents.constitution` ("decisions cite articles" is ceremony),
`gate.makefile-audit` (a reading, not a check; keep as a reconcile prompt), `gate.machine-reports`
(JSON beside the human report is pointless until something reads it — candidate).

**Python- or machine-specific, demoted to pack / host tool**: `gate.slots`, `gate.namespacing`
(a2kay's `container_slot.py`, one machine), `test.lineage`, `test.helper-smells`,
`test.mutation-prune` (method universal, cost 3–6 h; candidate), `test.subprocess-coverage`
(applies only if you spawn), `stack.strict-validation`, `ops.locks` (a code rule → lint or pack
note), `ops.logs` OpenTelemetry span per tool call (MCP pack), `gate.docker-rules` HEALTHCHECK
(services only; n/a for CLI images).

**Cargo cult for this owner**: `ws.hygiene-files` SECURITY.md / LICENSE on private repos;
`gate.machine-reports`; `agents.constitution`; claim/signal/source vault kinds in v0.1 (F7);
`kb.overview` as a separate checkpoint (it is the AGENTS.md map).

### 5.3 The v0.1 fifteen

Criterion, in this order: **universal across the four repo kinds · verifiable by a command · traced to
a named failure in the research.** Anything judge-only or single-stack drops to pack or runbook.

| # | checkpoint | verify | the failure it is traced to |
|---|---|---|---|
| 1 | `gate.clean-clone` — fresh clone, `bootstrap`, `check` green, wall time printed against a recorded budget | clone to tmp, run, time | a2kay CI drift; owner rows 26–27 (4 h prune, no ETA); `uv` picked 3.13 in a fresh worktree |
| 2 | `gate.one-command` — one runner, one gate word = lint + format + types + arch + every hermetic test; hooks and CI call it, never their own lines | diff hook config and workflow against the target | a2kay `ci.yml` drifted to a subset; owner row 1 (CI red, local green) |
| 3 | `gate.ci` — CI from the first commit runs the same command; every workflow checked by name after a push; "no CI" = recorded n/a with a revisit trigger | workflow file calls the runner; actions pinned to SHAs; `permissions:` | 9.5 days red unseen (fb:local-gate-must-match-ci) |
| 4 | `gate.one-hook-manager` — one hook owner, bd's `core.hooksPath` chained, proven by one real commit through the hooks | `git config core.hooksPath`; a commit in a tmp clone trips the guard | owner rows 2, 15 (hooks configured, never installed; beads vs pre-commit fought) |
| 5 | `gate.guards-have-red-tests` — every custom guard / fitness test has a planted-violation test in the repo | the tests exist and pass | fb:mutation-test-the-rules (a rule satisfied on 7 of 8 stacks by an unrelated env var) |
| 6 | `strict.preset` — the stack's strictest preset whole; warnings are errors; one formatter; every suppression in one file, scoped, with a reason and an expiry | preset drift tool / config diff | owner row 36; shelf `make preset` exists for Python |
| 7 | `arch.dag` — layers declared once in one file; enforced by an in-toolchain tool that reads that file; allowlisted edges carry reason + expiry | run the tool; count allowlist entries | owner row 36; a2web vs a2kay tool split; lifesim's design-reading form |
| 8 | `test.actor-surface-first` — behaviour tests at the real entry point, in process, in a controlled vocabulary with a checker, tagged `@spec`/`@bug`, written before the code | in-process driver exists; vocabulary file + checker; tag guard | 39/71 workflow bugs, 1/71 caught; 2/13 journeys; 201 → 68 phrases. **Supported by prediction** (§0) |
| 9 | `test.hermetic` — tmp HOME, app env scrubbed, no network, refusing fakes for OS services, fake model unless marked, parallel-safe with N workers, retries banned | run the suite with network off and N workers | real `~/.config` written; real `claude` CLI called; flaky test cost 143 min |
| 10 | `test.placement` — a placement table in AGENTS.md; extend before create; no file named after a change; one file per actor goal / per module | a test over test-file names vs change ids; file count delta per commit as a report | 67% of feat commits added a file; 24 named after a change |
| 11 | `test.lanes` — every hermetic test in the gate; a lane leaves it only for money / credential / rare resource, and then runs in CI by name | marker inventory vs the gate command | owner row 25; DES §3a-revised |
| 12 | `stack.pins` — toolchain version file, lockfile committed and installed frozen, upper bounds on deps, driven CLIs pinned | files exist; CI uses `--frozen`; bound check (shelf RG004) | `uv` 3.13 / `lxml`; RG004 rationale |
| 13 | `ws.secrets` — `.env` and secret files ignored, no tracked-but-ignored files, gitleaks on tree and history in the gate, visibility and secrets scheme recorded before the first push | gitleaks run; `git ls-files -i` | owner rows 23–24 |
| 14 | `agents.one-file` — one canonical AGENTS.md; client entry files resolve to it; content is a map (gate word, fix word, placement table, targets list, repo IS / IS NOT); no dated or roster data; always-loaded context measured against a budget | token count; a date/version grep outside generated files; symlink or import resolves | owner rows 10, 11, 18 (36k tokens of memory); ETH −3% / +20% (secondary) |
| 15 | `kb.homes` — bd wired, no second backlog; decisions as kernel-shaped files with rejected options, `decided_by`, `superseded_by`, pack version pinned, frontmatter gate; requirements in one declared home | `bootstrap-verify`; grep for `backlog.md`/TODO files; frontmatter check | owner rows 16, 17, 20, 21; lifesim 16 superseded decisions unchecked |

Not in the fifteen, by the criterion: everything in `shape.*` and `name.*` (runbook); mutation
pruning and lineage (pack tools); `gate.container` (measured, not prescribed); Docker rules (pack,
services only); the LLM, data and monorepo packs (§5.1) — written when the first project needs each,
resolution 0014's own trigger logic.

## 6. Ordering

### 6.1 New repo

Principle: **everything that will later block a commit is installed before the first line of code.**
Retrofitting a strict gate onto code is the "pre-existing drift" trap (owner row 14); on an empty
repo it is free.

1. Folder, git, visibility, secrets scheme, remote (`ws.*`) — before anything else, because a leak is
   the one irreversible failure (owner rows 23–24, 34).
2. Kickoff runbook: constraints, research with verdicts, name, stack decision, spikes with
   pre-registered outcomes — each step's output is a vault file (§3.3). Owner questions batched here,
   and only here.
3. Toolchain pins + lockfile + `bootstrap` target: fresh clone green with zero code (#1, #12).
4. The gate on an empty project: preset whole, formatter, types, arch tool with an empty DAG, hooks
   chained, CI running the one command (#2–#7). Each guard proven red with a planted violation (#5).
5. AGENTS.md as a map; knowledge homes wired (#14, #15).
6. Thin thread: one actor-surface scenario, the layer skeleton it crosses, the DAG declared from it
   (#8–#11). `lifesim #30`.
7. Features, each scenario-first.

### 6.2 Existing repo — order of fixing failures

Principle: **irreversible harm first, then stop the bleeding, then ratchets, then the expensive
restructure, then prose.**

1. Secrets and PII scan of tree and history; visibility recorded (#13). Irreversible if wrong.
2. The gate *exists*: one command, CI running it, hooks chained — at the repo's **current**
   strictness (#1–#4). Cheap; stops drift the same day.
3. Pins and lockfile (#12).
4. Strictness in ratchets — formatter, then linter, then types, each a whole-repo commit. **Sanction
   the one allowed carve-out here:** on a large legacy repo, strict types on day one means thousands
   of errors; the honest mechanism is one suppression file, scoped by path, each entry with a reason
   and an expiry (`strict.suppressions` + `ws.ignore-expiry`). That *is* a carve-out with a date. Say
   so explicitly in the DoD text, or the "no carve-outs" rule makes migration impossible and agents
   will route around it silently.
5. Actor-surface scenarios for the journeys (code-to-spec on live behaviour), journey coverage
   measured (#8–#11). Only now is the F3 question askable (§2).
6. Architecture DAG declared from reality with allowlisted violations carrying expiry, then tightened
   (#7). Unit-test sprawl pruned with mutation evidence (pack tool), after scenarios exist — never
   before, or the prune deletes the only tests.
7. AGENTS.md rewrite as a map; knowledge homes (#14, #15).
8. Decision on restart vs migrate, by the owner, from the §2.1 table.

## 7. What you are not thinking about

1. **Non-POSIX dev hosts.** lifesim is .NET/Godot. On Windows: symlinked CLAUDE.md (C4), `make`
   (C7), `flock` (`ops.locks`, `gate.slots`), `/dev/null` and `GIT_CONFIG_GLOBAL` in the hermetic
   git env, `~/.config`, the `$HOME` scrub — six checkpoints break. Either state "POSIX dev hosts" as
   a constraint of the skill (honest, and true today), or make each of the six mechanism-neutral.
   Recommendation: state the constraint in v0.1, with an expiry.
2. **The evidence base is one owner, five repos, one month, all pre-production.** Zero items on
   backups, migrations, data compatibility, API consumers, incidents. Blueprint will be run on the
   first repo with users without a single checkpoint about them (§5.1 item 7, 12). Add a
   `has-users` axis to `applies to` now, even with two checkpoints under it.
3. **The shelf is not in the fixture corpus.** Build order step 3 lists a2peer, lifesim, a2kay, a2web,
   a2db — not the shelf. The repo that dictates the ideal should pass it first; the machinery map
   already lists five defects it would surface (no Docker, DAG not ported, `linter-preset` gaps).
4. **Audit cost vs fix cost.** 181 checkpoints, each a file the agent opens, each with a verify
   command: an audit may cost more tokens and minutes than the fixes it finds. Round A owns the
   mechanism; the content answer is §3.3 and §5.3 — fifteen, then packs on demand.
5. **Client-specific facts inside client-neutral doctrine.** `.claude/settings.json`, `bd prime` on
   SessionStart, the Stop hook, `@AGENTS.md` imports are Claude Code facts; Codex and opencode read
   AGENTS.md and nothing else. A `client-claude` pack keeps the core honest.
6. **The needle leak** (§5.2) — the guard that protects privacy can publish the names.
7. **Who confirms the doctrine.** §0: the next 30 a2kay bugs classified by first-red test. Put it in
   the ledger as the fitness record the constitution asks for; blueprint's testing area expires if the
   number does not come in.
8. **Gherkin's reader is nobody.** Every rule inherited from BDD literature that assumes a
   non-developer reader (readability, business language) is dead weight here; keep only what the
   measurements support (vocabulary control, file per goal, tags).
9. **A passing audit has no stop condition.** Once everything is ✅, the agent's next move is
   gold-plating — adding packs, candidates, docs. The decay rule (principle 12) and the fifteen cap
   are the brake; say it in SKILL.md: after green, the only legal work is the product.

## 8. Question 7 — the five layers and the 25 pillars (design.md "Structure")

**Verdict on the five-layer decomposition (phase → pillar → checkpoint → stack answer →
evidence): ✅ supported as a shape, ⚠️ refuted as drafted in two places: the pillar list is the
python-uv tool inventory projected onto every stack, and "pillar" duplicates the inventory's "area"
as a second taxonomy.**

### 8.1 The layers

| layer | verdict | reason |
|---|---|---|
| 1 phase (when) | ✅ | It is the kickoff runbook of §3.3, named. Audit checkpoints must not depend on the phase; only runbook steps do |
| 2 pillar (point of view) | ⚠️ | The inventory already has 13 *areas* (`checkpoints/<area>/<id>.md`); the draft adds 25 pillars plus "non-stack pillars". Two taxonomies for one object means two indexes to keep derived and one more place for a checkpoint to be misfiled. **One taxonomy:** a checkpoint belongs to exactly one pillar; the directory is the pillar; the non-stack pillars are pillars too, with no stack row |
| 3 checkpoint (what) | ✅ | As before. Add the rule the draft implies but does not state: **a pillar exists only if a checkpoint reads it.** A pillar with no checkpoint (property tests, below) is a dead row every pack must fill for nothing |
| 4 stack answer (how) | ⚠️ | Right idea; the cell needs three states, not two (§8.4) |
| 5 evidence (why) | ✅ | With §0's "supported by prediction" marker as a legal evidence grade |

### 8.2 The 25 pillars, one by one

Criterion: a pillar is a *question every app stack has an answer to*, not a tool category the
python-uv shelf happens to contain. The answer column below only shows that *an* answer exists per
stack, from recall; by §8.4's own rule every one of those cells is **untested** until a repo runs it,
and none is a pack row.

| # | draft pillar | verdict | .NET / TS / Go / infra answer exists? | change |
|---|---|---|---|---|
| 1 | runtime and version pin | ✅ | `global.json` / `.nvmrc` or `.node-version` / `go.mod` `go` + `toolchain` directive / `flake.nix` or `.tool-versions` | — |
| 2 | dependencies and lockfile | ✅ | `packages.lock.json` (`RestorePackagesWithLockFile`) / `pnpm-lock.yaml` / `go.sum` / `flake.lock`, `.terraform.lock.hcl` | add "frozen install in CI" to the field list |
| 3 | task runner and gate word | ✅ | `just` or `make` everywhere; one per repo | — |
| 4 | formatter | ✅ | `dotnet format` / biome or prettier / `gofmt` / `nixfmt`, `terraform fmt` | — |
| 5 | linter, strictest preset | ✅ | Roslyn analyzers + `.editorconfig` severities / biome or eslint strict / golangci-lint / tflint, statix | — |
| 6 | types / compiler strictness | ✅ | `Nullable` + `TreatWarningsAsErrors` / `tsc --strict` / `go vet` + staticcheck / none (honest n/a for infra) | for compiled stacks 5 and 6 are one tool with two settings; keep both rows, the question differs |
| 7 | architecture enforcement | ✅ | ArchUnitNET / dependency-cruiser / go-arch-lint or depguard / module boundaries (weak) | **the python answer is wrong**: "pytest fitness tests; DAG not ported" — per C2 (§4) it is import-linter or tach, picked once |
| 8 | test runner | ✅ | xunit or NUnit / vitest / `go test` / none → "plan diff" | fold in: parallelism and speed (xdist / `Parallelizable` / vitest workers / `-parallel`), retries banned, the time budget |
| 9 | behaviour tests (Gherkin) and driver | ⚠️ rename, merge with 24 | scenario files + golden logs (lifesim) / Playwright fixtures / `testscript` / plan-diff | one pillar: **actor-surface scenarios and the in-process driver** (§1.3). The driver *is* the answer; "Gherkin" is the python-uv cell, not the pillar name |
| 10 | test isolation and doubles | ✅ | per stack; the question is universal | fold in: clock, randomness, process seams (§5.1 item 11) |
| 11 | coverage, following children | ✅ | coverlet / c8 or v8 / `go test -cover` (child following: untested for all three) / n/a | "following child processes" is a sub-field, not the pillar |
| 12 | mutation testing | ⚠️ candidate | Stryker.NET / StrykerJS (untested here) / weak in Go (untested) / n/a | keep only if `test.mutation-prune` stays a checkpoint; it is a pack tool in §5.2, so this row is a candidate pillar, counted but not required |
| 13 | property tests | ❌ not a pillar | FsCheck / fast-check / rapid — exist, but **no checkpoint reads this row** | a test *kind* like tables and goldens; fold into pillar 8 as "test kinds available: tables, property, golden/snapshot" |
| 14 | dependency hygiene (unused / undeclared) | ✅ | untested for .NET / knip or depcheck / `go mod tidy -diff` / n/a | — |
| 15 | spelling and docs lint | ❌ not a stack pillar | codespell is stack-neutral | move to a **universal tools** row answered once, outside the packs |
| 16 | security scans | ⚠️ split | gitleaks is stack-neutral → universal row. Vulnerability scan is per ecosystem: `dotnet list package --vulnerable` / `npm audit` or osv / `govulncheck` / osv on lockfiles | keep "dependency vulnerabilities" as the pillar; secrets go universal |
| 17 | hooks | ✅ | manager per pack (C6); the invariant is universal | — |
| 18 | container for the gate | ❌ not a pillar | a macOS host accelerator (§5.2) | demote to a python-uv pack note and a host-tooling recipe; the universal question underneath is "where is the gate reproducible from scratch" — that is CI (19) |
| 19 | CI | ✅ | one workflow calling the gate word; the stack bit is the setup action (`setup-dotnet` / `setup-node` / `setup-go` / nix) | — |
| 20 | packaging, release, install | ✅ | NuGet or `dotnet tool` / npm / goreleaser / "apply" (infra) ; Godot export for a game | depends on a **build** pillar that is missing (§8.3) |
| 21 | config and secrets loading | ✅ | `Microsoft.Extensions.Configuration` + user-secrets / dotenv + zod / envconfig or koanf / sops, agenix | — |
| 22 | errors | ✅ as a question | exceptions + result types / typed results / `errors.Is`/`As` conventions / n/a | an architecture decision more than a tool; the stack answer is "the idiom and the lint that enforces it" |
| 23 | logs and traces | ✅ | Serilog + OTel / pino + OTel / slog + OTel / n/a | — |
| 24 | entry surfaces and in-process driver | merge into 9 | | |
| 25 | shelf consumption | ⚠️ | only python-uv consumes shelf *packages*; every stack consumes shelf *skills* (blueprint itself) | reword: "how this repo pins the shelf: packages by git tag (python), skills by plugin version (all)". An honest near-n/a for non-Python, which is fine once the question is worded for both |

Net: 25 → **19 stack pillars** (merge 9+24, drop 13, 15 and 18 out of the stack axis, 16 split),
plus a universal-tools row (codespell, gitleaks) answered once.

### 8.3 Missing pillars

Each one is already demanded by a checkpoint in the inventory or in §5.1; the python-uv stack has
no build step and no store, which is why they were not seen.

| missing pillar | why it is a stack point of view | answers |
|---|---|---|
| **build / compile and the artifact** | for .NET, TS, Go the build is the first gate step and the thing packaging (20) ships; Python has none | `dotnet build` / `tsc` + bundler / `go build` / `nix build` or `terraform plan`; Godot export |
| **persistence and migrations** | §5.1 item 7; every stack has an idiom | EF Core migrations / Prisma or drizzle / goose or migrate / alembic (python) / n/a |
| **validation / schema strictness** | `stack.strict-validation` (owner row 30) is already a "stack pack" row with no pillar | pydantic strict / FluentValidation / zod / go-playground validator |
| **workspace / monorepo layout** | §5.1 item 10; uv workspace, `.sln`, pnpm workspaces, `go.work` | — |
| **dev host and target OS** | §7.1: six checkpoints break on Windows; a pack must say which hosts its answers were proven on | POSIX only (python-uv today) / Windows + macOS (lifesim) |

Two items are not pillars but **fields on every pillar answer** that the draft field list lacks:
*output format for agents* (`strict.agent-output`: concise lint format, `skip_covered`, `-v`) and
*wall time on the reference machine* (the gate budget).

### 8.4 "A stack pack is complete only when it answers every pillar" — does it hold?

✅ as a forcing function — the pack gets the same "not set up" verdict a repo gets, and a half-pack
cannot ship. Two conditions, or it fails:

1. **Three cell states, not two.** "Tool" or "n/a with reason" leaves no honest value for a cell
   nobody has run. The dotnet pack is "provisional" by the owner's own word; lifesim proves perhaps
   half its rows (gate, analyzers, ArchUnitNET, scenarios, lefthook/just, no CI). The rest would be
   invented — the thing the doctrine forbids ("extracted, never invented"). Add **untested** as a
   cell state, shown and counted like a candidate checkpoint, and require the *proving repo* on every
   answered cell. Complete = no empty cell; untested cells are visible, not hidden behind a guess.
2. **The pillar set is picked by repo kind before the stack answers it.** Count the honest n/a's
   under the draft 25: .NET app ~3, TS app ~2, Go CLI ~3, **infra ~11** (no types, no arch, no test
   runner, no coverage, no mutation, no property, no entry surface, no packaging). A pack that is
   40% "n/a" is not incomplete; the pillar set is wrong for it. Infra is a different *repo kind*,
   not a different stack — the same way a library has no entry surface and a game has no HTTP.
   Make `repo kind` (app / library / CLI / game / infra) the axis that selects the pillar set, and
   `stack` the axis that answers it. Factory's app-scoped criteria in a monorepo (R4) is the
   precedent. Without this, agents learn to type "n/a" as a reflex and the forcing function dies.

With both conditions the rule holds for .NET, TS and Go. For infra it holds only after the
repo-kind axis exists; until then the infra pack would be a list of n/a's and the audit would be
wrong in both directions (failing a healthy homelab repo on pillars it cannot have, passing it on
`ops.declarative-infra`, which is the one that matters there).

### 8.5 Fields on a pillar answer

The draft's seven (tool + version · config location · strictest settings and why · target · seen
failing once · alternatives refused · evidence) are right; "seen failing once" must point at the
planted-violation test (§4, `gate.guards-have-red-tests`), not at a memory. Add: output format for
agents · wall time · proving repo · cell state (answered / n-a / untested). Drop nothing.
