# Checkpoint inventory — draft 1 (2026-10-10)

Every candidate checkpoint, deduplicated across the sources, before any is written as a skill file.
This is the input to Fable rounds A–B and to the owner round; it is not the skill.

**Sources.** `A` a2peer kickoff checklist (`A-own` = the owner asked for it, `A-agt` = added by an
agent or Fable) · `L` lifesim bootstrap checklist (`L-own` / `L-agt` / `L-fab`) · `H` a2kay testing
handoff (session input, not in the repo; numbers checked in research/a2kay-testing.md) · `P`
prior art (agent-harness, agent-weiss: [research/prior-art.md](research/prior-art.md)) · `K`
knowledge and kickoff research ([research/knowledge-and-kickoffs.md](research/knowledge-and-kickoffs.md))
· `S` already shelf doctrine or tooling.

**Where enforced** (principle 13): `gate` = the repo's own `make check` fails without it ·
`audit` = blueprint checks it each run · `judge` = needs intent; asked or decided and recorded.

**Conflicts between sources** are marked ⚠️ and listed at the end.

## 1. Shape before code

| id | checkpoint | source | where |
|---|---|---|---|
| shape.research | How others solve the problem is researched and written down; nothing chosen from memory | A-own, L-own | judge |
| shape.verdicts | Each research claim carries supported / refuted / untested; one-pass findings say provisional | A-agt, L-agt | audit |
| shape.cross-check | A claim a decision rests on has a second, independent pass | L-agt, H | judge |
| shape.constraints | Hard constraints stated up front | A-own | judge |
| shape.lanes | Problem split into lanes where deployment differs (local vs server) | A-own | judge |
| shape.targets | Target machines named; the weakest sets the budget | L-agt | judge |
| shape.spikes | Risky choices have spikes, ordered, each naming the decision it settles and ending in a written verdict that updates that decision | A-agt, L-own, L-agt | audit |
| shape.spike-trigger | Spike or research before settling when: the claim is a number; sources disagree; the tool is new; being wrong costs a rewrite | L-agt | judge |
| shape.decisions | Decisions recorded with who decided (owner / agent / Fable), the owner's own words, and what each supersedes | A-agt, L-own, L-agt | audit |
| shape.open-decisions | Open decisions listed apart from taken ones, numbered, repeated until answered | A-agt, H | audit |
| shape.refused | Refused options recorded with the reason | A-agt, L-agt | audit |
| shape.second-opinion | A second model (Fable) reviews the design before build | A-own, H | judge |
| shape.tos | Terms of service checked for every external service the project drives | A-agt | judge |
| shape.threat-model | What data leaves the machine to which vendor, what input is untrusted, what can run commands | A-agt | audit |
| shape.value-claim | If the project rests on an unproven benefit, every use and its outcome is logged from day one | A-agt | judge |
| shape.platform-catches | A file of known platform / version differences, effect and mitigation | L-own | audit |

## 2. Name

| id | checkpoint | source | where |
|---|---|---|---|
| name.clash | No clash on npm, PyPI, Homebrew, GitHub, MCP registry | A-own, A-agt | judge |
| name.plain | A plain word the audience knows (EN + RU, UK, TR, ES speakers); no bad meaning in those | A-own, A-agt | judge |
| name.house | House convention where it applies (`a2` + noun for agent tools); short, since it becomes a tool prefix | A-agt | judge |
| name.deliverable | Names say the deliverable, not the origin (shelf resolution 0008) | S | judge |

## 3. Workspace and hygiene

| id | checkpoint | source | where |
|---|---|---|---|
| ws.location | Repo under `~/Workspaces/<name>`; session moved there | A-own | audit |
| ws.git | git initialised; `.gitignore` from the stack's templates | A-agt, P | audit |
| ws.secrets-ignored | `.env` and secret files ignored; no tracked-but-ignored files | P | gate |
| ws.secret-scan | gitleaks (tree + history) in hooks or gate | P | gate |
| ws.dep-scan | Dependency vulnerability scan (osv-scanner) | P | gate |
| ws.ignore-expiry | Every ignore / suppression list entry carries an expiry date | P, S | gate |
| ws.secrets-env | Secrets from the environment only; subprocess calls in list form | A-agt | gate (ruff `S`) |
| ws.privacy | No real names (owner, clients, relatives) in fixtures, docs, metadata, commits; package metadata names the organisation | H | audit |
| ws.hygiene-files | README with a one-line purpose; SECURITY.md; LICENSE | A-agt | ⚠️ P says ❌ existence checks — audit content instead |
| ws.remote | Git remote set; `bd dolt remote add` so beads syncs | A-agt | audit |
| ws.commit-policy | Commit and push only on the owner's explicit approval; never commit files an agent is still writing | A-agt, L-agt, H | audit (AGENTS.md text) |

## 4. Backlog and knowledge

| id | checkpoint | source | where |
|---|---|---|---|
| kb.beads | Beads initialised after the shelf guard (`make bootstrap` ordering); hooks chained, config read back | A-own, S | gate (`bootstrap-verify`) |
| kb.parked | Parked ideas go to the backlog, not into scope | A-own | judge |
| kb.blocked | Waiting on the owner → `--status blocked` + a comment; deferred carries its trigger | A-agt, S | audit |
| kb.openspec | Requirements and change proposals in openspec | A-agt, K | audit |
| kb.vault | Decisions, options, research, probes (spikes), questions, sources as a2kay kernel-kind files; slug ids; interim frontmatter gate until `a2kay validate` (owner, 2026-10-10) | A-agt, K | gate (frontmatter check) |
| kb.supersede | A replaced decision is marked superseded, points to the new one the same day, and documents quoting it are swept | L-agt, K | audit |
| kb.glossary | Every coined name glossed by its job on first use | A-agt | audit |
| kb.overview | One-page overview linking the decision records; design drafts moved into entities | A-agt | audit |
| kb.homes | One job per system: ideas → options, work → beads, decisions → vault; nothing lives only in chat | A-agt, L-agt | audit |
| kb.bug-on-sight | A bug found while writing tests is a bead at once, and the scenario carries `@known_bug:<id>` | H | audit |

## 5. Shelf

| id | checkpoint | source | where |
|---|---|---|---|
| shelf.onboarded | `make bootstrap` run; guard, resolver block, beads, preset all `verified` | S | gate (`guard`, `preset`) |
| shelf.seam | Before writing substrate glue: catalog checked, ADOPT (DEEP · STABLE · WINS) by git tag, never a local path | A-agt, S | gate (`guard`) + judge |
| shelf.not-adopt | What the project must NOT adopt from the shelf, and why | A-agt | audit |
| shelf.promote | Generic substrate promoted to the shelf when written (three triggers); test doubles in the owning package's `testing` module | H, S | judge |
| shelf.release-flow | Sibling packages consumed by tag, never editable path; release = commit + tag, then repoint | H, S | gate (`guard`) |

## 6. Stack and pins

| id | checkpoint | source | where |
|---|---|---|---|
| stack.decision | Stack decided explicitly and recorded | A-own, L-own | audit |
| stack.five-tests | Tools picked by: fits the stack; used together widely; well known to models; real user reports incl. complaints; shipped track record | L-own | judge |
| stack.pins | Toolchain / SDK pinned in one file; package versions central; upgrade = one diff | L-fab | audit |
| stack.upper-bounds | Dependency pins with upper bounds; external CLIs the project drives pinned to tested versions | A-agt, S (RG004) | gate |
| stack.instructions-current | Top-level agent instructions updated the same day the stack changes | L-agt | audit |

## 7. Strictness

| id | checkpoint | source | where |
|---|---|---|---|
| strict.linters | Strictest linters available, every warning an error | A-own, L-own | gate |
| strict.preset | Python: the shelf ruff preset whole, drift gated by `make preset` | A-agt, S | gate |
| strict.types | Type checker at its strict preset | A-agt, S | gate ⚠️ ty vs pyrefly |
| strict.complexity | Complexity ceiling (mccabe 12 in the shelf preset) | A-agt, P, S | gate |
| strict.formatter | One formatter | L-own, S | gate |
| strict.banned-apis | Banned-API lists per rule, applied by project, not per-file pragmas | L-fab | gate |
| strict.suppressions | Every suppression in one config, scoped by path, with a reason | L-fab, S | gate |
| strict.proven-red | Each gate made to fail once on purpose before it is trusted | L-fab | audit |
| strict.agent-output | Tool output tuned for agents: concise lint format, coverage `skip_covered` + `branch`, strict markers | P | gate (preset) |

## 8. Architecture

| id | checkpoint | source | where |
|---|---|---|---|
| arch.structure | Codebase structure decided up front | A-own | audit |
| arch.layers | Layers by dependency direction (core types/protocols, no IO → adapters/store → orchestration → entry points); lower never imports upper; sibling adapters never import each other | A-agt, L-agt | gate |
| arch.enforced | Layering enforced by a tool, not prose | A-own, L-own | gate ⚠️ tool choice |
| arch.reads-design | The architecture test reads the design's own dependency list | L-fab | gate |
| arch.ports | Every external system behind a protocol / port in core; that port is the mock seam | A-agt, L-agt | audit |
| arch.composition-root | Dependency injection at one composition root | L-own | audit |
| arch.presentation-split | Logic runs and is tested without the presentation layer | L-own | audit |
| arch.domains | Code and tests in a fixed set of noun domains; verbs in file names, never folder names | H | audit |
| arch.patterns-early | Patterns from day one, even when they look heavy; optimise only what is measured | L-own | judge |
| arch.one-process | One process first, behind the boundary a later split will use | L-own | judge |
| arch.structured-data | Saves and logs store structured data; text for people is rendered from it | L-own | audit |
| arch.errors | Error taxonomy decided once (shelf `a2effect`), not per module | A-agt | audit |

## 9. Testing (H numbers checked in [research/a2kay-testing.md](research/a2kay-testing.md); several were overstated)

| id | checkpoint | source | where |
|---|---|---|---|
| test.usecases-first | Behaviour scenarios first (Gherkin), one `.feature` per actor goal, driven through the real entry point in process | A-own, L-own, H | gate |
| test.steps-vocab | A fixed step vocabulary (STEPS.md); generic steps carry most scenarios; steps assert only what the actor sees | H | gate (planned guard) |
| test.tags | `@spec:` / `@bug:` traceability; `@known_bug:<id>` strict xfail; `@pending` skip (shelf `bdd-tags`) | A-agt, H, S | gate |
| test.placement | Placement table in AGENTS.md: highest level that can observe the behaviour; extend a file before creating one; never name a file after a change | H | audit |
| test.unit-tables | Unit tests only for single-function rules, written as tables; pairwise, not full product | H | audit |
| test.mutation-prune | A test is deleted only with mutation evidence; a ledger records each deletion | H | audit |
| test.lineage | Tests aimed at each function ranked; top ones are refactor targets | H | audit ⚠️ tooling only in a2kay |
| test.helper-smells | Every test helper classified (awkward API / unused fixture / scenario fragment / missing shared tool / space saving) | H | audit |
| test.hermetic | Autouse hermetic env: temp HOME and config, git through env, app env vars cleared, refusing fakes for OS services, fake models unless marked | H, P | gate |
| test.process-boundary | Fake at the process boundary, not the port, so own policy still runs; real-world layer has its own domain + a small contract suite | A-agt, H | audit |
| test.lanes | Unit / integration (default) / vendor (opt-in, cost-capped, out of the gate) | A-agt | gate |
| test.goldens | Real outputs captured once, byte for byte; format pinned by tests | A-agt, L-agt | audit |
| test.no-nightly | Every scenario runs in the gate; a break surfaces in the commit that caused it | H | gate |
| test.ports-zero | Ports always 0; never bind-then-release | H | audit |
| test.subprocess-coverage | Coverage and mutation follow child processes | H | gate |
| test.determinism | Same seed → same log hash; save → load → same next ticks (where the product is a simulation) | L-agt | gate |
| test.coverage-gate | Coverage floor in `make check`, not the inner loop; diff-coverage against main | A-agt, P | gate |
| test.thin-thread | One thin vertical thread through every layer before any feature | L-fab | audit |
| test.first-feature | A first feature per domain written before the code it describes | H | audit |

## 10. Gate, hooks, CI, containers

| id | checkpoint | source | where |
|---|---|---|---|
| gate.one-command | One task runner, one gate word (`make check`) = lint + types + tests with coverage + architecture | A-agt, L-fab, S | gate |
| gate.whole-repo | Done = gate green over the whole repo, no carve-outs | H, S | audit (AGENTS.md text) |
| gate.hooks-call-runner | Hooks call the task runner, never their own command lines | L-fab, P | audit |
| gate.hooks-installed | Hooks installed and live, not just configured; respect `core.hooksPath` | P, S | gate (`bootstrap-verify`) |
| gate.hooks-staged | Commit hooks check staged content, not the working tree | H | audit |
| gate.fast-local | Local gate fast, one word, no machine-specific step; machine-specific checks get their own command | L-fab | audit |
| gate.container | Gate runs in a Linux container when Docker answers; in place in CI and without Docker; container is an accelerator, never a requirement; never nest | H | audit |
| gate.slots | Heavy container jobs share N slots through kernel locks; heavy targets print wall time and load | H | audit |
| gate.namespacing | Container image / volume names per worktree | H | audit |
| gate.ci | CI from the first commit runs the same `make check`, one reusable workflow (a2web `gate.yml`) | A-agt, K, P | audit |
| gate.ci-pinned | Actions pinned to SHAs; `permissions:` block | P | gate |
| gate.makefile-audit | Makefile has no bypassed tools, duplicated work, stale or conflicting targets | P | audit |
| gate.machine-reports | Every heavy tool writes JSON next to the human report | H | audit |
| gate.docker-rules | Dockerfile: non-root USER, HEALTHCHECK, deps before source, cache mounts, no secret ENV/ARG; compose: healthchecks, restart, loopback binding, pinned images | P | gate (hadolint) + audit |

## 11. Agent instructions

| id | checkpoint | source | where |
|---|---|---|---|
| agents.canonical | `AGENTS.md` canonical; `CLAUDE.md` a symlink to it | A-agt ⚠️, K, S | gate |
| agents.content | AGENTS.md says what the repo IS / IS NOT, hard constraints, the gate, the fix command, hooks, the shelf resolver block, the placement table, privacy, commit policy | A-agt, P, H | audit (content, not existence) |
| agents.per-folder | Short per-folder guidance pointing at one structure rulebook | L-fab | audit |
| agents.constitution | The a2 / shelf constitution adopted; decisions cite its articles | A-agt, S | audit |
| agents.question-format | Questions to the owner: numbered, context first, a recommendation "yes" accepts; batched | L-agt | audit (AGENTS.md text) |
| agents.ask-only-owners | Ask the owner only taste, scope, priority, risk, money, outward-facing; decide the rest as the agent | L-agt | audit |
| agents.no-fake-answers | Never record an answer the owner did not give; agent choices labelled the agent's | L-agt, H | audit |
| agents.escalation | Escalate when: scope or a ranked principle changes; owner decisions conflict; a spike contradicts a decision; anything leaves the machine | L-agt | audit |
| agents.worktrees | Parallel agents in separate worktrees and branches; disjoint files; cross-check after a parallel batch | L-agt, H | audit |
| agents.phases | Phases with exit checks: decide → spike → bootstrap → thin thread → features | L-agt | audit |
| agents.dod-per-bead | Definition of done per bead: tests, gate green, decision or spec updated | A-agt | audit |

## 12. Release and operations

| id | checkpoint | source | where |
|---|---|---|---|
| ops.release | Semver tags, CHANGELOG, install path (`uv tool install` / `uvx`), config location (`~/.config/<name>`) | A-agt | audit |
| ops.logs | Structured logs; OpenTelemetry span per tool call (a2mcp pattern) | A-agt | audit |
| ops.dogfood | The tool registered in the owner's own agent sessions as soon as one path works | A-agt | judge |
| ops.agent-ergonomics | Tool names and descriptions tested with a real agent (a2web `eval` pattern) | A-agt | audit |
| ops.locks | Serialise with kernel locks (flock), never plain lock files | H | audit |

## Conflicts to settle

| # | conflict | sources | lean |
|---|---|---|---|
| C1 | Type checker: a2peer list says `ty`; the shelf preset switched ty → pyrefly on 2026-09-12 | A-agt vs S | pyrefly (shelf preset is the reference); a2peer list is stale |
| C2 | Architecture enforcement: a2peer says import-linter or tach; shelf resolution 0005 says native pytest fitness tests, and the layer DAG is not ported yet | A-agt vs S | Fable B; if the shelf has no DAG rule, promoting one is a shelf bead |
| C3 | Hygiene files: a2peer wants LICENSE / README / SECURITY.md; prior art rejects existence checks | A-agt vs P | audit content (purpose line, security contact), not existence |
| C4 | Symlink direction: a2peer checklist has CLAUDE.md canonical; shelf has AGENTS.md canonical | A-agt vs S | AGENTS.md canonical |
| C5 | State: lifesim wants `bootstrap.yaml`; shelf "one job per system" says beads | L-agt vs S | Fable A (F1) |
| C6 | Hooks manager: lifesim uses lefthook; shelf ships a native hook installer and refuses foreign managers but names where to add | L-own vs S | Fable B |
| C7 | Task runner: lifesim `just`; shelf and every a2 repo `make` | L-fab vs S | per stack pack; `make` for python-uv |
| C8 | Lifesim has no CI by recorded decision; a2peer list wants CI from the first commit | L vs A-agt | CI by default; "no CI" is a recorded not-applicable with its reason |

## 13. Added from the owner's past corrections (R6, one pass: [research/owner-corrections.md](research/owner-corrections.md); row numbers refer to that file)

| id | checkpoint | source | where |
|---|---|---|---|
| gate.local-covers-ci | `make check` runs every step CI runs (diff the workflow against the Makefile); after a push every workflow is checked by name, never inferred from another green one | R6 rows 1, 4 | audit |
| gate.ci-down-loud | A blocked or red CI is reported as critical; no manual workaround | R6 row 3 | audit (AGENTS.md text) |
| gate.no-test-outside | No nightly-only or manual-only suites; every test kind runs in `make check` (same as test.no-nightly) | R6 row 25, H | gate |
| gate.time-budget | Gate and mutation runs are timed against a recorded budget; a breach is a finding | R6 rows 26, 27 | audit |
| agents.context-budget | Always-loaded context (AGENTS.md, its imports, project memory) measured; over budget is failing | R6 row 18 | audit |
| agents.no-instance-data | AGENTS.md holds no dated or roster data (dates, versions, package counts) outside generated files | R6 row 11, S | gate (mechanical) |
| kb.one-backlog | No `backlog.md` / TODO lists beside beads | R6 rows 20, 21, S | gate (mechanical) |
| kb.decision-complete | Each decision names the rejected options, why, and its primary evidence | R6 rows 16, 17 | gate (vault frontmatter) + audit |
| ws.pii-guard | Gate fails on client, people or owner names in tracked files; history scanned once before a repo goes public | R6 row 23, H | gate |
| ws.visibility | Public / private and the secrets scheme decided before the first push | R6 row 24 | judge |
| gate.one-hook-manager | One hook framework; beads and the shelf guard chained into it, proven by a real commit | R6 row 15, P, S | gate (`bootstrap-verify`) |
| arch.quirks-colocated | Known quirks recorded next to the component they describe | R6 row 6 | audit |
| arch.env-parity | Declared env vars equal the ones the code reads | R6 row 7 | gate |
| arch.guard-needles | A guard takes its needles from the population it protects, never from an unrelated config list | R6 row 33 | audit |
| arch.typed-seams | Typed contracts at package seams, so an upgrade breaks at lint time | R6 row 13 | gate (types) |
| stack.strict-validation | Validation preset where required fields reject empty values | R6 row 30 | stack pack |
| gate.docker-one-image | One published image; build cache in CI and locally | R6 rows 8, 22 | audit |
| ops.dep-updates | Dependency updates on a scheduled job; no paid service added without the owner's yes | R6 row 9 | audit |
| ops.declarative-infra | Infra repos declarative only; no state created by hand over SSH | R6 row 5 | audit (infra pack) |
| gate.make-everything | A Make target for every routine command, listed in AGENTS.md | R6 row 37, P | audit |
| ws.merge-policy | Merge policy recorded per repo (solo repo → direct to main) | R6 row 38 | judge |

Anti-pattern seed from R6: CI workaround · pushing on a local-only green · pre-existing-drift
carve-out · nightly-only tests · unit-test sprawl · Gherkin written last · dated data in AGENTS.md ·
second backlog · rule that cannot fire · guard sourced from config · manual host state · paid service
added unasked · decision without rejected options.
