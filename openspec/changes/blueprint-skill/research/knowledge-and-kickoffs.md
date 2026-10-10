# Knowledge system + kickoff conventions — research for `blueprint`

Read-only survey, 2026-10-10. Sources: a2kay `main` (ADR 0042, 0043, 0046; `docs/design/repo-mode-experience.md`,
`docs/design/game-design-ontology.md`; `src/a2kay/bootstrap/packs/kernel/`), a2peer, lifesim, a2web, a2db, shelf, aggre.

**Headline:** repo-vault mode is **designed, not built**. Every engine piece is an open bead under epic
`a2kay-fmj1`. No repo has a `.a2kay/` vault dir in its design folder; nothing validates lifesim's 247 decisions.
The blueprint must prescribe the *file shape* now and the `a2kay validate` gate as a placeholder that turns on later.

## (a) Vault ontology for software projects

### Engine state (a2kay, main)
- `a2kay init [--pack kernel|k|none] [--vault PATH]` exists (`src/a2kay/__main__.py` `_run_init` → `app.init_vault`).
  Writes `.a2kay/` (config, `ontology/*.yml` copied from the pack, `pack.yml` = vault marker), a `.gitignore`
  managed region, `.gitattributes`. Idempotent; runs no git. Default pack `kernel` (or `$A2KAY_PACK`).
- `a2kay doctor` = `graph doctor`: lints every file with the write rules. Needs the full install (ML stack: torch,
  transformers, anyembed[llamacpp]); heavy for pre-commit/CI.
- **Not built** (beads, all open): `fmj1.9` repo storage mode (`storage = "repo"`: never commit/push/LFS);
  `fmj1.10` serverless `a2kay validate` (no ML install, pre-commit + CI, `file:line: error … -> fix`);
  `fmj1.11` slug ids instead of `{id}`/`{n:04}` counters; `fmj1.12` repo vault overrides kernel kind paths without
  copying the kind; `fmj1.13` inline items (`owner#id` addresses); `fmj1.14` `validate --code` (rule ids named in
  tests exist; rules without tests reported); `fmj1.15` worktree-aware index; `fmj1.16` generated indexes.
- `.a2kay/config.toml` `storage = git|icloud|dropbox|syncthing|repo` is decided (ADR 0046 §5), not built (`fmj1.4`).

### Decided rules for repo vaults (ADR 0046 §10–15)
- Repo vault = a folder in the project repo (`design/`), `storage = "repo"`; repo git + PRs are history/review.
- Direct file edits allowed (MCP-only is personal-vault only); **validation is the guard**: whole vault in
  pre-commit, merge commit in CI. A new required field ships optional first.
- **Ids are slugs, never counters** (two worktrees both minting `0007` merge silently).
- Repo carries its own kinds in `.a2kay/ontology/`, overlaid on kernel, never redefining kernel fields
  (ADR 0042 §2); may redefine a kernel kind's *path*. Kinds move to a shared pack at the 2nd repo.
- Routing: **reachability decides** — anything an agent in this repo needs goes in the repo vault, craft included.
  Links go personal → repo only; repo never links into a personal vault.
- AGENTS.md block for a2kay ≤5 lines. Generated indexes must not be committed from every PR (conflicts).

### Kernel pack kinds (`src/a2kay/bootstrap/packs/kernel/pack.yml`)
person, project, research, source, call, artifact, signal, claim, option, decision, question, probe, register,
register_item, capture, journal. Four layers (ADR 0043): documents (`source`, `call`, `artifact`) → what happened
(`signal`) → what we believe (`claim`) → what we do (`option`, `decision`, `question`, `probe`).

Kernel paths below are personal-vault defaults; a repo vault overrides them (see lifesim layout). Status
`classes` map statuses to live/open/done.

| kind | kernel path | job (`when_to_use`) | fields (req*) | status enum (default) | conditions |
|---|---|---|---|---|---|
| decision | `{parent}/decisions/{n:04}-{slug}.md` | a choice made; not-yet-made = option | title*, status, date, decided_by `owner\|session`, evidence set[claim], chooses/refuses set[option], consequences, revisit_trigger, executed_by set[register_item], superseded_by link[decision], stage | accepted\|superseded\|reversed (accepted) | superseded ⇒ superseded_by |
| option | `{parent}/options/{id}-{slug}.md` | something we could build/do | title*, status, evidence/counter_evidence set[claim], depends_on set[option], refused_because, revisit_trigger, built_in, superseded_by, stage | proposed\|designed\|partial\|built\|refused\|parked (proposed) | refused ⇒ revisit_trigger |
| research | `Researches/{slug}/README.md` (container) | an inquiry; an undertaking is a project | title*, status, horizon `bounded\|ongoing`, stages; children decision/artifact/signal/claim/option/question/probe/register/journal | open\|concluded\|dropped (open) | — |
| probe | `{parent}/probes/{id}-{slug}.md` | spike/experiment; outcomes written before it runs | title*, **tests*** set[claim], settles set[question], result set[signal], status, stage | open\|running\|done\|abandoned (open) | running/done ⇒ body section `Outcomes`; done ⇒ result |
| question | `Questions/{id}-{slug}.md` or `{parent}/questions/…` | an unknown | title*, **kind*** `blocking\|request\|tension`, status, positions set[claim\|option], blocks set[option\|claim\|decision], addressed_to, answered_by link[decision\|probe\|signal] | open\|answered\|dissolved (open) | answered ⇒ answered_by |
| source | `Sources/{slug}.md` | a doc someone else wrote; one per URL (`unique: [url]`) | title*, source_type, url, date, fetched, provided_by, origin, note, strength | strength ladder felt<asserted<reported<documented<measured (reported) | — |
| claim | `Claims/{id}-{slug}.md` / `{parent}/claims/…` | could be wrong: hypothesis, finding, need | title*, status, confidence, evidence/counter/rejected set[signal\|source\|call\|artifact], depends_on, contradicts, expires, superseded_by | open\|supported\|contested\|refuted\|retired | refuted ⇒ counter_evidence |
| signal | `{parent}/signals/{slug}.md` | dated observation/measurement; cannot be wrong | title*, date*, nature, value, unit, attributed_to, strength, status, superseded_by | live\|superseded\|withdrawn | superseded ⇒ superseded_by |
| artifact | `Docs/{slug}.md` / `{parent}/artifacts/{slug}.md` | a doc we wrote, read whole | title, doc_type (brief, memo, method, report, constitution…), status, strength, superseded_by | draft\|working\|delivered\|superseded | superseded ⇒ superseded_by |

Body guidance (kernel `guidance`): decision = Y-statement first ("In the context of …, facing …, we decided …,
to achieve …, accepting …"), then Context / Decision / Consequences. option = What it is / How it works / Status
today / Alternatives rejected / Trail. research = Findings (first) / Question / Why now / Approach. probe = What we
test / Outcomes (before running) / Method / Result / Trail. question = Question / Positions / What would settle it /
Trail. claim = Claim / Reasoning / Falsifier / Cheapest test / If true then / Trail. source = What it is /
Takeaways / Quotes.

**Supersession** is a field, not a file move: `status: superseded` + `superseded_by: <kind>/<id>` (enforced on
decision, signal, artifact; optional on option, claim). lifesim also writes a reverse `supersedes:` (10 files) —
not a kernel field. ADR 0046 W6: "make reversal cheap"; the sweep of files still quoting the old decision is manual.

**Links:** frontmatter = bare `kind/slug` (`system/needs`) — the graph's edges; body = relative markdown links
(GitHub-renderable), no wikilinks in repo vaults.

### Product-design pack (repo-local, lifesim; `game-design-ontology.md`)
- `pillar` (`pillars/{slug}.md`): title*, rank* int, status accepted|retired, superseded_by. Body: Statement, Demands, Forbids.
- `system` (`systems/{slug}.md`): title, facet* `player|tech`, status candidate|accepted|retired, serves set[pillar]
  (req. when player), depends_on set[system], content_dir, config_path, requirements list[requirement].
  Body: Intent, Model, Requirements, Tuning notes, Open questions. `accepted` needs ≥1 accepted requirement citing an
  owner decision; **an agent never accepts its own requirement**.
- `requirement` inline in system frontmatter: id* `<system>.R<n>` (never reused), title*, status
  candidate|accepted|implemented|retired, decided_by set[decision], superseded_by. Prose under `### needs.R1 — title`
  with SHALL sentence + GIVEN/WHEN/THEN scenario.
- Not kinds: vision/loops/glossary/runbooks = `artifact` doc_type; numbers live in `content/` or config, never prose;
  open questions = system section + a bead when blocking (kernel `question` refused there: a second queue).
- Interim (engine missing): decisions use `about: [system/x]` and `derived_from: [research/x]` instead of
  `evidence: [claim/…]` — **both non-kernel fields**; a future `validate` would flag them.

### Software-project mapping (what the blueprint's ontology section should say)
| need | home | kernel kind |
|---|---|---|
| work item, spike ticket, blocker | beads | — |
| requirement + change proposal | openspec `specs/`, `changes/` | — (lifesim used inline `requirement` instead; pick one) |
| ADR | vault `decisions/` | decision (Y-statement, decided_by, superseded_by, revisit_trigger) |
| idea / alternative / refused path | vault `options/` | option (refused ⇒ revisit_trigger) |
| research report | vault `research/<slug>/README.md` | research |
| spike | vault `probes/` (outcomes pre-registered) + a bead to do it | probe (tests* claim) |
| unknown | vault `questions/` only when not blocking work; blocking → bead | question |
| external doc | vault `sources/` | source |
| glossary, runbooks, overview | vault root / `runbooks/` | artifact doc_type glossary/method |

## (b) a2peer & lifesim as built (2026-10-10)

### a2peer — skeleton only
- 1 commit (`bd init`). Untracked `docs/design.md` (135 lines, draft; "Decisions taken" as prose bullets) and
  `docs/project-setup-checklist.md` (119 lines — the raw material for this skill).
- `.beads/` with 7 beads (6 spikes P1 + remote mode P3). `.claude/settings.json`: SessionStart `bd prime` only.
- AGENTS.md and CLAUDE.md are **separate files**, both bd-generated; CLAUDE.md has "_Add your build and test commands
  here_" placeholders. Nothing project-specific.
- Missing vs its own checklist: no vault (`design/`, `.a2kay/`), no openspec, no glossary, no Makefile, no
  pyproject/ruff/ty/import-linter, no pre-commit, no CI, no LICENSE/README/SECURITY, no shelf resolver block, no git
  remote / `bd dolt remote`. Spikes exist only as beads — no probe files with pre-written outcomes. Decisions are
  bullets in a draft, with no decided_by/supersedes fields (checklist §1.7 asks for both).
- Checklist §8.2 says "CLAUDE.md with AGENTS.md as a symlink to it" — **the reverse** of shelf and lifesim.

### lifesim — mature design vault, code gate fresh
- Commits: research import → shelf consumer + beads → "migrate knowledge base to the a2kay game-design ontology" →
  grilling rounds → gate 1. Large untracked set: the whole C# solution, ~150 decisions, runbooks, checklist.
- `design/` (repo vault in target shape, **no `.a2kay/`**): decisions 247 (`YYYY-MM-DD-slug.md`), options 70, pillars
  5, systems 19, research 37 dirs, runbooks 3, vision/loops/glossary. Field census, decisions: title/status/date/
  decided_by/about 247, derived_from 101, superseded_by 16, supersedes 10, chooses 4, refuses 6. Options: about 70,
  revisit_trigger 50, derived_from 44, refused_because 8.
- AGENTS.md (CLAUDE.md symlink): shelf resolver block, 2 bd blocks, then a lifesim-owned section: vault rules
  ("implement only `status: accepted`", "numbers live in content/", agents record choices `decided_by: session`),
  beads status-mapping table, `bd remember` override, beads-sync caveat (no remote).
- Gate: `justfile` (`check: fmt-check build test content`, `test-fast`, `content`, `godot-import`, `hooks`);
  `lefthook.yml` calls `just` recipes only; installed by appending to `.beads/hooks/pre-commit` because bd owns
  `core.hooksPath`. **No CI by decision** ("the gate runs on the owner's machines"). Strictness: Directory.Build.props
  warnings-as-errors, 3 BannedSymbols files, ArchUnitNET reading `depends_on` from `design/systems/*.md`.
- Tests: `tests/scenarios/*.yaml` (design sentence + seed + expectations), `Sim.Scenarios` (golden logs),
  `Sim.Architecture`, `Sim.Properties`.
- `.claude/settings.json`: SessionStart `bd prime` + Stop hook warning on in_progress beads (a2peer lacks the Stop hook).
- Bootstrap plan + checklist: `design/research/project-bootstrap-plan/README.md`, `docs/project-bootstrap-checklist.md`
  (47 items; item 32 proposes `bootstrap.yaml` — **never created**).
- Gaps: plan promises `src/AGENTS.md`, `tests/AGENTS.md` — absent. No openspec (requirements live inline in systems).
  No vault validation (`tools/kb_check` idea → a2kay, unbuilt); 16 superseded decisions unchecked. Non-kernel fields
  (`about`, `derived_from`, `supersedes`) everywhere. No git remote; beads sync dead.

### Inconsistencies between the two
| axis | a2peer | lifesim |
|---|---|---|
| CLAUDE.md | separate file, bd template | symlink → AGENTS.md |
| requirements | openspec (planned) | inline `requirement` in system |
| spikes | beads only | research dirs (`ecs-spike/`) + prototype/ code; no `probe` kind |
| decisions | prose bullets in a draft | 247 files, dated slugs, decided_by |
| gate | none | `just check` + lefthook, no CI |
| CI | checklist says "from first commit" | refused by decision |
| shelf block | absent | present |
| Stop hook | absent | present |
| bootstrap state | none | proposed, never made |

## (c) Makefile / CI / Docker conventions

### Target names (Python repos)
| target | a2kay | a2web | a2db | shelf | aggre |
|---|---|---|---|---|---|
| check (the gate) | guard preset lint typecheck archlint spell deps test | lint ty test-cov arch | lint test security | guard preset lint format typecheck spell deps test(+cov) | lint test |
| bootstrap | uv sync | uv sync --all-extras | uv sync + prek install | yes (+bootstrap-verify) | uv sync + prek install |
| lint | ruff check + format --check | ruff + pymarkdown | agent-harness lint | ruff | agent-harness lint |
| format / fix | format | fix | fix | format | fix |
| typecheck | typecheck (pyrefly) | ty (ty) | — | typecheck (pyrefly strict) | — |
| arch | archlint (import-linter) | arch (tach + tests/architecture) | — | — | — |
| test / test-fast | test (cov floor 90, xdist) / test-fast | test / test-cov (85) | test | test / cov | test (ephemeral postgres via compose) |
| other | spell (codespell), deps (deptry), preset, guard, clean, dev | coverage-diff (95), bless-wire, build, dev, eval* | security, coverage-diff, build | catalog, advisory, sync | audit, dev |
Common core: **`bootstrap`, `check`, `lint`, `fix|format`, `test`**, plus a typecheck and an arch target.
Pattern: lint targets never modify files ("safe for AI, CI, pre-commit" — aggre); `fix` does. Slow/real-env lanes
(`test-browser`, `eval-*`) stay out of `check`. a2kay comments: "Definition of Done — the full gate, no carve-outs".
`guard`/`preset` exit 2 = "CANNOT VERIFY, not a pass".

### CI shapes
- **shelf** `check.yml`: push main + PR → setup-python 3.12, setup-uv (cache), `uv sync`, `make check`. Cleanest.
- **a2web**: `gate.yml` (`on: workflow_call`, pinned uv 0.10.12, `uv sync --all-extras`, `make check`) called by
  `ci.yml` (push every branch + PR) and `release.yml` (`v*` tag → gate again + browser-gate → GHCR image publish).
  Rationale in file: "a duplicated gate drifts". Also `actionlint` pre-commit hook.
- **a2kay** `ci.yml`: **drifted** — runs ruff/pyrefly/coverage individually (no guard/preset/archlint/spell/deps, no
  floor), still `sed`s out an a2kit path source that the repo retired. Counter-example.
- **a2db** `publish.yml`: tag only; inline ruff+pytest, then PyPI trusted publishing (`id-token: write`). No push CI.
- **aggre** `ci.yml`: `make lint` + `make test` with a `services: postgres` container and `AGGRE_TEST_DATABASE_URL`.

### Docker
- Images (a2kay, a2web): multi-stage builder → slim runtime, pinned uv image, assets baked for offline, non-root
  (a2web), `/health` route, volumes for data. Published only from a tag after the gate (a2web → GHCR).
- **Docker for gates:** only for test dependencies, never to run the linters. aggre `make test`: if
  `$X_TEST_DATABASE_URL` unset, start `docker-compose.test.yml` on a random free port with a per-checkout project
  name, run pytest, `down -v`, keep exit code; CI provides the DB as a service and sets the env var instead.
  reelm `check` validates compose (`docker compose config --quiet`) and runs conftest policies on Dockerfile/compose.
  a2web pre-commit: actionlint.
- Pre-commit runner: `.pre-commit-config.yaml` with `repo: local` + `language: system` calling `uv run …`
  (a2web, a2db), installed via `prek` (fallback pre-commit); heavy checks (`ty`) at `stages: [pre-push]`.
  lifesim: lefthook → `just` recipes. bd owns `core.hooksPath` (`.beads/hooks/`) in every beads repo — a hook
  manager must chain into it, not replace it (lifesim friction note §1).

## (d) Recommendations for `blueprint`

1. **Four homes, one job each: beads = work, openspec = requirements + changes, vault = why (decision, option,
   research, probe, question, source), glossary = vocabulary.** Why: both kickoffs named this split; lifesim shows the
   failure when a home is missing (requirements migrated into the vault inline). Audit rule: an item living in two
   homes is a finding.
2. **Vault path `docs/` subfolder or `design/`, one name per repo, layout fixed:** `decisions/ options/ research/<slug>/
   probes/ questions/ sources/ runbooks/ glossary.md overview.md`, plus `.a2kay/config.toml` (`storage = "repo"`).
   Why: ADR 0046 §10/§13 and the lifesim layout; kernel default paths (`Researches/`, `Sources/`) are personal-vault.
3. **Decision = kernel `decision` fields exactly**: title, status accepted|superseded|reversed, date, decided_by
   owner|session, chooses/refuses, revisit_trigger, superseded_by; body Y-statement → Context/Decision/Consequences.
   Why: lifesim invented `about`/`derived_from`/`supersedes`; a later `a2kay validate` will reject or ignore them.
   If a "about this area" link is needed, add it as a declared repo-local overlay field, not ad hoc.
4. **Ids = dated slugs (`YYYY-MM-DD-slug.md`) for decisions, slugs elsewhere — never `0001-` counters.** Why: ADR 0046
   §12, parallel worktrees. Note the conflict: a2kay/a2web `docs/adr/NNNN-*` and shelf `docs/resolutions/NNNN-*` use
   counters; the blueprint should leave existing ADR dirs alone and use slugs for new vaults.
5. **Supersession = same-day two-way update**: old gets `status: superseded` + `superseded_by`; sweep files quoting
   it (lifesim checklist #41). Why: the only enforced condition today is superseded ⇒ superseded_by; the sweep is the
   recurring manual miss.
6. **Spike = `probe` file with Outcomes written before running + a bead to execute it; result closes the bead and
   updates the decision it settles.** Why: a2peer has spikes as beads only, lifesim as research dirs; neither records
   pre-registered outcomes, which is the kernel's only probe condition.
7. **Blocking question → bead; non-blocking unknown → `question` file or a system/spec "Open questions" section.**
   Why: lifesim refused `question` as a second queue; beads already own blocking.
8. **Glossary = types only, banned synonyms, every coined name glossed by job.** Why: shelf and lifesim both run it;
   a2peer checklist §9.4.
9. **Gate the vault now with a cheap stand-in, swap for `a2kay validate` when `fmj1.10` ships.** Stand-in: a
   frontmatter check (required fields, enums, superseded ⇒ superseded_by, links resolve) in `make check`. Why: 16
   superseded decisions and 247 files in lifesim are unchecked; "a gate never seen red is a hypothesis".
10. **One gate word: `make check` (Python) / `just check` (other stacks); hooks and CI call it, never their own
    command lines.** Why: a2kay CI drifted from `make check`; a2web's `gate.yml` and lifesim's lefthook→just both exist
    to stop drift.
11. **Standard targets: `bootstrap check lint fix test test-fast typecheck arch`**; `lint` never writes; slow/real-env
    lanes outside `check`; guards exit 2 on "cannot verify". Why: the intersection of 5 repos.
12. **CI: one reusable gate workflow** (`gate.yml`, `workflow_call`, pinned uv) called from push-every-branch CI and
    the tag release. Why: a2web's design is the only one that has not drifted; shelf's is the minimal version.
    "No CI" (lifesim) is allowed only as a recorded decision with a revisit trigger.
13. **Docker only where tests need services**: compose file per test env, random port, per-checkout project name,
    env-var override that CI fills with a `services:` container. Why: aggre pattern works locally and in CI without
    running linters in a container.
14. **Hooks must chain into bd's `.beads/hooks/`** (bd sets `core.hooksPath`); audit `git config core.hooksPath`.
    Why: lifesim friction §1; `lefthook install`/`prek install` would replace the guard + bd hook.
15. **AGENTS.md canonical, CLAUDE.md a symlink to it;** project-owned section outside every managed block; ≤5-line
    a2kay block; shelf resolver block. Why: shelf + lifesim do this; a2peer has two drifting files and its checklist
    states the reverse direction; a2web uses `@AGENTS.md`, a2kay two hand-kept files.
16. **`.claude/settings.json`: SessionStart `bd prime` + Stop hook warning on in_progress beads.** Why: lifesim has
    both, a2peer only the first.
17. **Checked-in bootstrap state file** (`bootstrap.yaml`: step, status todo|doing|done|blocked-owner, output path,
    exit command). Why: lifesim checklist #32/#45 asked for it; neither repo has one, and a2peer stalled after step 3
    with no record of where.
18. **Every agent-made choice recorded `decided_by: session`; requirements never self-accepted.** Why: lifesim
    checklist #35 and the system condition in the product-design pack; both kickoffs flagged answers mislabelled as owner's.
