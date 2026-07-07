# The Shelf — exploration capture (2026-07-07)

> **Status:** thinking, not implementation. Captured from an `/opsx:explore` session.
> **Working name:** `shelf` (repo, under the `yoselabs` org). **Branding deferred** on purpose.
> **Provenance:** this explore session + R154 (AI software factory strategy) + the `micro-software`
> K skill + 5 read-only adversary agents (topology · contract-governance · reuse-directive ·
> catalog-build-vs-adopt · a2kay-inheritance mining).
>
> **Homes when instantiated:** ~~doctrine + ontology → Kay~~ — **superseded by [resolution 0002]
> (../resolutions/0002-doctrine-homes-in-the-shelf.md): everything homes in the shelf; consumers
> reference it, if necessary. Kay is not a runtime dependency.**

---

## 0. TL;DR

Build ONE shared repo (`shelf`) that houses small, individually-ownable, contract-guaranteed
software pieces ("micro-software"), consumed by separate apps (a2kay, a2web, …) via git-tag pins.
It is the **N=1 execution** of R154's factory — housed centrally for build speed, not a doctrine
revision. ~70% of the governance is already designed (R154) or already built (a2kay); the shelf
mostly *subtracts* and *inherits*.

---

## 1. The concept (naming deferred)

- Essence: **small software pieces that are easy to OWN, composed rather than framework'd.**
- The differentiator is **ownability + composability + contract-guarantee**, NOT smallness. A future
  name should point at that, not at "micro".
- Lineage: microservices / micro-frontends, but the axis is *ownability*, not distribution.
- "micro-software" is a working label only. Branding is a separate pass (no throwaway brand names).
- Individual pieces can overlap/"clash" in responsibility → handled by the lifecycle arcs
  (supersede / absorb / merge) + promotion discipline, not by fiat.

---

## 2. Two-concepts reframe + relation to R154

Two distinct things were merged in the original ask; they are already pried apart in the corpus:

- **Concept 1 — micro-software (the `micro-software` skill + primitive-shelf):** the DECOMPOSITION
  doctrine. Already executed: `anyllm · anyembed · convert-md · git-porcelain` + T0 primitives.
- **Concept 2 — the AI factory (R154):** the NETWORK — contracts, ledger, promotion, decay.

Map of "new worry today" → "already-decided R154 term":
- "define asks / why we need it" → the **contract** (intent + typed I/O + acceptance scenarios).
- "who owns / who requested" → **named human sponsor** per request AND verdict.
- "some tests immutable" → **holdout scenarios** held by an independent judge.
- "shape can differ from contract" → **"unit of selection is the contract, not the code"** (code =
  regenerable phenotype, contract = gene, ledger = fitness record).
- "lineage if renamed" → the **ledger** (append-only) + lineage arcs.
- "log version per use case" → **binding mode** field + ledger provenance.
- "don't kill others' use cases" → **breaking-change-ships-migration** + NO-GO scope assertion.
- "add a dep instead of writing code" → the **regenerate-vs-request crossover** / build-vs-adopt.

Only genuinely-new things vs R154: (a) the **central-monorepo topology** (R154 assumed distributed
producer repos — but a single shared repo is centralization, *not* the distributed game R154 warned
about, so NO doctrine revision), and (b) **test-governance granularity** (which tests are load-bearing
vs disposable, who may delete one, how a contract survives a `rename`/`arg→struct`).

---

## 3. Resolutions (decisions made this session)

### R1 — Topology: hybrid (shelf repo + internal workspace + git-tag versions)
- The 4 packages live in ONE new repo (`shelf`), kept as an **internal uv workspace**
  (`workspace = true` UNCHANGED) so all packages are edited atomically — the inner loop is preserved.
- Versions = **namespaced git tags** (`anyllm-v0.2.0`). No PyPI, no publish step beyond `git push --tags`.
- Consumers (separate repos) depend **across the boundary**:
  ```toml
  [tool.uv.sources]
  anyllm = { git = ".../shelf", subdirectory = "packages/anyllm", tag = "anyllm-v0.2.0" }
  ```
  `uv.lock` pins the commit → reproducible.
- **Hard rules:** tags are non-negotiable (bare `{git}` silently tracks HEAD — the real footgun);
  **never delete an old tag** (old consumers stay pinned → evolution is opt-in → "no silent break");
  **don't absorb the apps** into the monorepo (forces one resolved version across all apps forever,
  killing the v1-here/v2-there case git-ref pinning handles free).
- **a2kay becomes just another consumer** — its `[tool.uv.sources]` must flip from `workspace = true`
  to `{git, subdirectory, tag}` the day the packages move, or `uv sync` breaks.
- ⚠ Unverified: the side-by-side local dev-loop ergonomics (path-override when both repos are checked
  out, flip to tag for commit). **Smoke-test before trusting.**

### R2 — The contract is the unit; the test is its executable arm
- Durable unit = a **file** (`<pkg>/contracts/*.yml`), not a bare `@pytest.mark.protected`.
- One contract = **capability + invariants + binding (one line) + shape flag + acceptance→test +
  holdout→consumer-repo + owner + requester + status + expires**.
- **Shape is a flag, not a separate concept:** `shape: flexible` (facade absorbs rename/arg→struct,
  the default) | `shape: pinned` (signature IS the contract — only when serialized / passed to a 3rd
  lib / hot-path; changing it = major bump + migration).
- **Two hats:** OWNER controls shape (may churn freely); REQUESTER controls retirement (may not
  silently delete a past demand). Retirement = sponsor-gated status flip in the same diff.
- **Protection is EARNED, not granted:** every contract is born `status: candidate` (INERT — cannot
  block a refactor). It becomes `active`/protected ONLY when a live consumer demonstrably breaks
  without it. This is what makes "full scaffold up front" safe from the calcification-freeze.
- Anti-Goodhart for a solo shop (one agent writes refactor + test): **holdouts live in the consumer
  repo, run against the PUBLISHED artifact, in CI the refactor agent never sees** + mutation testing.
- Integrates with R154 (does NOT duplicate it): the file IS a ledger row (`ledger_ref`), `acceptance`
  = R154 visible scenario, `holdout` = R154 unrevealed judge scenario, `sponsor` = R154 named human,
  the "nothing-else-changed" CI check = R154 NO-GO assertion.

### R3 — A micro-software IS a build-vs-adopt evaluation harness (the crown insight)
- The **contract is provider-agnostic; the implementation is swappable.** A contract's test suite is
  a standing tender: any candidate — our own code OR a third-party dep — that goes green can win.
- Adds one ontology entity: **`Implementation` (ours | third-party | hybrid-adapter)**, under the
  Contract. The micro-software = "the contract + whichever implementation currently wins."
- Winning end-state: our code **dissolves into a thin adapter over a qualifying dep** — not a failure,
  the ultimate "stop caring" (exactly what `anyllm` did for LLM providers, generalized).
- Makes R154's Rule 5 (build-vs-adopt) **continuous & executable**, not a one-time human judgment.
- Retires the earlier "adopt even if imperfect" self-sabotage: you adopt on GREEN, never on hope.

### R4 — The reuse directive: three-gate, earned by a passing test
- Keep the intent (reach for the shelf FIRST; improve-once-benefit-everywhere). Kill "reuse even if
  larger/imperfect" — it *instructs* the wrong abstraction (contradicts the skill's Rule 3/5 + Metz).
- The gate: **adopt a shelf item ONLY IF ① DEEP (hides real complexity) ② STABLE (settled API)
  ③ WINS (weight-vs-saved favors it).** Any gate fails → duplicate locally.
- The three-gate picks *candidates*; the R3 contract tests *adjudicate* them.
- **Home:** the `acc` metacognitive layer (a before-you-act judgment), referencing the `micro-software`
  skill for depth. **Enforcement:** a CI shelf-note gate — any new hand-rolled helper must reference a
  shelf entry OR carry a one-line "checked the shelf, didn't win because ___". CI enforces that the
  check happened; it cannot judge depth — acc + the skill supply the judgment.

### R5 — Catalog = derived projection; build nothing called a "catalog"
- Per-capability verdicts: discover → QMD + grep (ADOPT); propose-change → OpenSpec (already yours);
  own/who-owns → CODEOWNERS + git-blame; version/release → git tags (+ release-please only later);
  reference-graph → uv dependency edges. The **only** genuinely-new datum is **who-requested** (a
  manifest field + optional ledger line).
- The "catalog with discover/evaluate/propose/own" framing IS the UDDI grave R154 killed — but a
  PERSONAL monorepo catalog at N=1 is a legitimately smaller object (no strangers, no publication
  incentive). Rename it: **the manifest shelf + the request ledger.**
- Two R154 laws honored: **promotion-not-publication** (a piece gets a manifest only when a 2nd
  consumer pulls it) + **mandatory decay** (TTL; auto-deprecate the unreused).
- Do NOT build: a registry, discovery service, web UI, capabilities DB, a 2nd propose-change system,
  a versioning system, a reference-graph builder, Nx/moon/Pants.

### R6 — Conflict-minimization BY STRUCTURE (borrowed from your own systems)
- **Files are the source of truth; every index/catalog is a DERIVED projection, never hand-edited.**
  (This is a2kay's Vault→Graph pattern and Kay's memory-files→MEMORY.md pattern.)
- One concept per file (one use case, one contract, one primitive). Two parallel agents each ADD a
  file → git merges disjoint adds cleanly → zero conflict, no locks, no concurrency control.
- **Append over mutate.** A new file beats editing a shared list.

### R7 — The constitution (small on purpose; a long constitution is already failing)
```
I.   Files are the unit of truth; every index/catalog is DERIVED, never hand-edited.
II.  One concept per file — one use case, one contract, one primitive.
III. Append over mutate. A new file beats editing a shared list.
IV.  Structure controls size, not caps. A large file is a SMOKE ALARM that a structural boundary
     is missing (a pattern un-applied) — the response is to find the missing boundary, never to swing
     a line-count axe. Size may TRIGGER a design review; it is never itself the law.
V.   Protection is EARNED. Contracts are born `candidate` (inert) until a live consumer breaks
     without them.
VI.  Reach for the shelf first; adopt only if DEEP · STABLE · WINS; else duplicate.
VII. Promotion, not publication. A thing enters the catalog when a 2nd consumer pulls it.
VIII.Decay is mandatory. TTL + auto-deprecate the unreused; deletion is a virtue.
```
Seeded from a2kay's AGENTS.md (whole-codebase DoD, no carve-outs) + glossary discipline +
primitive-shelf rule-of-three + OpenSpec ritual.

### R8 — Glossary strictness: TYPES only, never instances
- **Litmus:** "Would this entry still exist if we deleted every single package?" YES → glossary
  (bounded ~15 concepts, fixed). NO → it names a specific piece → manifest/catalog, never the glossary.
- The glossary is bounded by the size of the ONTOLOGY, not the size of the shelf. `anyllm` never
  appears; `MicroSoftware`/`Capability` do. (a2kay's glossary already obeys this exactly.)

### R9 — Linter preset: strictest, a2kay-derived, decoupled from a2kit
- Lift nearly verbatim: ruff select-set `F,E,W,I,N,UP,B,C4,PIE,PTH,RUF,SIM,ARG,PERF,RET,TID,PL,ANN,A`
  (line-length 140, py311), `ruff format --check` as its own gate, `ty`, PEP-735 dev-group
  hermeticity, `make check` whole-codebase no-carve-out DoD, pytest `--strict-markers`.
  `A` (flake8-builtins) is load-bearing — it enforces the builtin-named-concept convention.
- The **boundary AST test is the spine** (~20 stdlib lines): each shelf package forbids importing any
  consumer app. Ship it as a shelf-provided pytest helper. (a2kay: `packages/*/tests/test_*_boundary.py`.)
- **Reimplement** the substrate-neutral a2lint rules (AK200 layer-DAG, AK201–205 import discipline,
  AK209 test-mirror, AK214 no-`dict[str,Any]`) as the shelf's own tiny AST lint. DO NOT depend on
  a2lint (lives in a2kit; half its rules assume a FastMCP-server shape → would re-couple the shelf).
- The preset itself is shelf micro-software: `Kind: config-preset`, consumed by every repo.

### R10 — docs-as-system structure
```
docs/
  thoughts/     ← raw explorations (dated, unresolved, freely messy)
  tracks/       ← a durable line of work (topology, contract-governance, …)
  missions/     ← a scoped objective within a track (OpenSpec changes attach here)
  resolutions/  ← decided things (ADR-style: fork, choice, why, expiry)
  constitution.md · glossary.md   ← the two standing docs
```
Thoughts feed tracks; tracks spawn missions; missions close into resolutions (a resolution with an
expiry = beliefs-with-expiry).

### R11 — Naming: deferred to a separate branding pass.

---

## 4. The ontology spine (glossary-style chain; updated with `Implementation`)
```
Shelf ─ the repo; the corpus of shared micro-software                     (≈ Vault)
  └─ MicroSoftware ─ one reusable unit                                     dir = identity
       ├─ Kind ─ primitive | any-lib | composite | cli | framework | config-preset
       ├─ Tier ─ T0 primitive · T1 any-* · T2 composite                   (T3 Product is OUT — the apps)
       ├─ Release ─ a git tag; the version
       └─ provides ▸ Capability ─ the stable "stop-caring" promise
             ├─ realized-by ▸ Implementation ─ ours | third-party | hybrid-adapter   ← swappable (R3)
             ├─ guaranteed-by ▸ Contract ─ durable I/O promise + invariants          ← the GENE (own file)
             │     ├─ bound-to ▸ Shape ─ current surface (names, signatures)          ← phenotype; flexible|pinned
             │     ├─ verified-by ▸ AcceptanceScenario ─ visible executable test
             │     └─ verified-by ▸ HoldoutScenario ─ hidden test in CONSUMER repo, vs published artifact
             └─ satisfies ▸ UseCase ─ concrete demand: why THIS consumer needs it     ← own file
                   ├─ requested-by ▸ Consumer ─ an app (edge = its pyproject git-pin)
                   ├─ sponsored-by ▸ Sponsor ─ the accountable human (named)
                   ├─ owned-by ▸ Owner ─ controls SHAPE (CODEOWNERS)
                   └─ retired-by ▸ Requester ─ controls RETIREMENT (the two hats)

  Lifecycle (state):  candidate → active → deprecated → retired            (+ orphaned)
  Lineage (arcs):     renamed-from ▸ · absorbed-into ▸ · merged-with ▸ · supersedes ▸
  LedgerEntry ─ append-only: request → delivery → verdict → cost           (R154 fitness record; later)
```
**Open fork:** model this ontology AS a2kay EntityTypes (get derived catalog, graph_query, dangling-
reference validation, QMD search for free — knowledge in K, code in shelf) vs. flat manifest files in
the shelf. The a2kay-entities path is the deepest expression of "build nothing."

---

## 5. Inheritance map (condensed from a2kay mining)

| a2kay asset | Verdict | Note |
|---|---|---|
| Ruff strict preset (`ANN`+`A`) + `make check` DoD + PEP-735 hermeticity | GENERALIZE / INHERIT | The "strictest-linter" deliverable; near-verbatim. |
| Boundary AST tests (`packages/*/tests/test_*_boundary.py`) | GENERALIZE | **The spine.** Invert for the shelf. ~20 stdlib lines. |
| a2lint AK200 layer-DAG · AK201–205 import discipline · AK209 test-mirror · AK214 | GENERALIZE (reimpl) | Substrate-neutral; DON'T depend on a2kit. |
| a2lint MCP-surface rules (AK002/003/207/210–213, tool-budget) | A2KAY-SPECIFIC | Assume a FastMCP server. |
| `core/atomic_io.py`, `core/duckdb_sidecar.py`, `core/managed_region.py` | GENERALIZE | The 3 founding T0 primitives. |
| `anyllm`, `anyembed`, `convert-md`, `git-porcelain` | GENERALIZE (done) | Already AST-guarded; move as-is. |
| primitive-shelf ledger + rule-of-three + micro-software doctrine | INHERIT-AS-PATTERN | The shelf's founding governance. |
| OpenSpec discipline · glossary one-name design | INHERIT-AS-PATTERN | Workflow + convention, not a2kay's content. |
| ontology engine `core/schema.py` · Vault→Graph projection · `core/uri.py` etc. | A2KAY-SPECIFIC | The product's guts (pattern may inherit, impl stays). |

**Founding day-one contents:** 4 packages + 3 T0 primitives + linter preset + boundary-test helper.

---

## 6. Open forks / next steps
1. **Smoke-test the side-by-side dev loop** (20 min) before trusting the git-tag topology. (R1 ⚠)
2. **Capture homes:** doctrine + ontology → Kay (link to R154); operational docs → shelf/docs when the
   repo exists. (This file is the pre-repo draft of both.)
3. **Ontology fork (§4):** a2kay-entities vs flat manifest files. Worth one more explore pass.
4. **v1 scope chosen = FULL SCAFFOLD** (topology + contracts + catalog.md + acc directive + catalog
   skill) — made safe by R2's candidate-by-default (scaffold present, protection inert until earned).
5. **NOT decided:** branding; whether the linter preset is a config-preset vs a CLI; release-please
   adoption timing (defer until release cadence hurts).

## 7. Links
- R154 (AI software factory strategy) — the parent doctrine; this is its N=1 execution.
- `micro-software` K skill — the decomposition method (stop-caring litmus, deep-module guardrail,
  build-vs-adopt gate, tier model, any-* COMPUTE-vs-STATE law, rule-of-three shelf).
- a2kay — donor of generalizable code + first consumer; MUST NOT be imported by the shelf.
