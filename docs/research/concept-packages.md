# Concept packages — grouping the shelf into stdlib-shaped domains

- **Status:** research (2026-10-10). Not a resolution. If accepted, it becomes one resolution plus
  one RECONCILE pass per group.
- **Question:** should the shelf stop minting one package per helper and group pieces into
  concept packages (`any-file`, `any-time`, `any-mcp`, …) that a perfect stdlib would offer?
- **Verdict:** ✅ for the cheap end of the shelf: dependency-free or light primitives with one
  consumer, where the per-package cost (a pin, a tag, a manifest, a use-case, a lock entry) is larger
  than the code. ❌ as a blanket rule. Heavy-dependency `any-lib`s, pytest plugins and the
  fast-churning composite stay alone. 50 packages become 27, and 25 after two deprecations.

## 1. Why now: the evidence

The consumers have already documented the problem. Two comments in consumer manifests show that
the per-package model leaks today:

- **a2kay `pyproject.toml`:** "page-tsv and lean-wire must name the SAME tag." Tags are namespaced
  per package but repo-wide: each tag is a snapshot of every package. page-tsv depends on lean-wire,
  and uv resolves that transitive dependency from page-tsv's own checkout. So if the consumer names
  two different tags, it gets two URLs for one package name, and uv refuses to resolve. a2kay pins
  page-tsv **at lean-wire's tag** to get around this.
- **a2web `pyproject.toml`:** "anyllm is intentionally NOT pinned here." llm-cache pulls anyllm in
  transitively, so a direct anyllm pin collides ("conflicting URLs for anyllm"). a2web therefore
  cannot choose its own version of anyllm.

The common cause: **every intra-shelf dependency edge forces a consumer to pin both ends at one
snapshot.** The edges today:

```
any-frontmatter  -> yaml-merge        (extra [merge])
content-extract  -> convert-md
http-cache       -> sqlite-resource
llm-cache        -> anyllm
mcp-result-wire  -> page-tsv -> lean-wire
```

Merging the two ends of an edge into one package removes the hazard for good. A group that takes
one end and leaves the other keeps it.

There is a second symptom, the "no obvious home" one. The crash-safe tempfile + fsync + replace
write exists **three times**: in `atomic-io`, privately in `any-frontmatter/document.py`, and
privately in `dir-trust`. The authors of the second and third copies did not reach for a 37-line
package. A helper needs a home that someone will open while they look for it.

## 2. Inventory

`API` = length of `__all__`. `src` = Python lines under `src/`, docstrings included. Consumers are
the actual pins and imports in a2kay and a2web, not only the catalog's derived column.
Dependency weight: **none**, **light** (a pure wheel, < 1 MB), **medium** (compiled, or a few MB),
**heavy** (tens of MB or more).

| Package | Does | Runtime deps (weight) | Consumers | Ver | API | src |
|---|---|---|---|---|---|---|
| a2effect | typed failure kind → wire envelope + prose | pydantic (medium); `[testing]` pytest, pytest-bdd | a2kay, a2web | 0.3.0 | 9 | 1169 |
| any-browser | one protocol over headless engines | none; `[patchright]` `[zendriver]` (heavy) | a2web | 0.1.0 | 9 | 1175 |
| any-file | safe names, root-held refs, binary sniff, media type, slug, secret patterns | anyascii (light) | a2kay | 0.2.0 | 16 | 440 |
| any-frontmatter | YAML frontmatter that keeps comments, layout-free version hash | ruamel.yaml (medium); `[merge]` yaml-merge | a2kay | 0.1.0 | 19 | 378 |
| any-markdown | wikilinks with code excluded, sections, chunks | markdown-it-py (light) | a2kay | 0.3.0 | 13 | 851 |
| anyembed | embedding backends | torch, transformers, numpy (heavy); `[llamacpp]` | a2kay | 0.4.0 | 5 | 553 |
| anyllm | LLM provider choice, fallback, cost | none; SDK extras | a2kay; a2web (transitive only) | 0.7.0 | 22 | 1397 |
| asgi-token-gate | ASGI token-header middleware | none | a2kay | 0.1.0 | 10 | 138 |
| async-scope | async teardown, lazy thunks, cancellable thread | none; `[asgi]` uvicorn | a2kay, a2web | 0.3.0 | 5 | 388 |
| atomic-io | crash-safe text write | none | a2kay | 0.1.0 | 1 | 37 |
| bdd-tags | pytest plugin for Gherkin tags (`pytest11` entry point) | pytest, pytest-bdd (runtime) | a2kay | 0.1.0 | 6 | 49 |
| browser-cookies | read the local browser cookie stores | none; `[read]` browser-cookie3 | a2web | 0.1.0 | 5 | 235 |
| content-extract | web page → markdown + metadata + headings/links | convert-md (shelf), trafilatura (medium), selectolax (medium) | a2web | 0.3.0 | 5 | 346 |
| convert-md | documents → markdown | trafilatura, html2text; `[pdf]` `[documents]` (heavy) | a2kay; a2web (transitive) | 0.10.0 | 17 | 824 |
| dir-trust | folder content-hash trust grants | ruamel.yaml (medium) | a2kay | 0.1.0 | 3 | 125 |
| dom-schema | declared CSS extraction that says why it came back empty | selectolax (medium) | a2web | 0.1.0 | 5 | 198 |
| duckdb-sidecar | DuckDB connect, lock and index rules | duckdb (heavy) | **none live**: a2kay use-case active, no pin, no import | 0.3.0 | 4 | 197 |
| due-schedule | is an interval/cron job due | croniter (light) | a2kay | 0.1.0 | 6 | 117 |
| event-bus | in-process typed pub/sub | none | a2kay | 0.1.0 | 1 | 71 |
| fts-query | search-box text → FTS5 query | none | a2kay | 0.1.0 | 12 | 222 |
| git-porcelain | git subprocess + credential fidelity | none | a2kay | 0.5.0 | 38 | 906 |
| html-fragment | HTML blob → markdown/text | lxml (medium) | a2web | 0.1.0 | 2 | 159 |
| http-cache | conditional-GET cache | sqlite-resource (shelf) | a2web | 0.1.0 | 6 | 197 |
| http-fetch | GET with browser TLS impersonation | curl_cffi (medium) | a2web | 0.3.0 | 4 | 276 |
| json-in-html | LD-JSON / microdata / OG / `window.__X__` from HTML | selectolax (medium) | a2web | 0.2.0 | 10 | 801 |
| json-match | dotted-path JSON compare for test steps | none | a2kay | 0.1.0 | 6 | 101 |
| jsonl-log | rotating append-only JSONL log | none | a2kay | 0.1.0 | 8 | 178 |
| launchd-agent | macOS LaunchAgent plist + launchctl | none | a2kay | 0.2.0 | 14 | 256 |
| lean-wire | line-safe TSV codec + pruning | pydantic (medium) | a2kay, a2web | 0.3.0 | 6 | 240 |
| llm-cache | sqlite TTL cache for completions | aiosqlite (light), anyllm (shelf) | a2web | 0.1.2 | 3 | 181 |
| llm-wobble | single funnel for untrusted LLM JSON | none | a2kay, a2web | 0.5.1 | 14 | 456 |
| managed-region | replace a marker-delimited block | none | a2kay | 0.1.0 | 1 | 55 |
| mcp-arg-errors | FastMCP middleware: bad arguments → typed fault | fastmcp (heavy), pydantic | a2kay | 0.1.0 | 4 | 106 |
| mcp-bridge | stdio → HTTP MCP proxy that outlives restarts | fastmcp, httpx | a2kay | 0.1.0 | 4 | 100 |
| mcp-clients | find MCP clients and read their server lists | none | a2kay | 0.1.0 | 6 | 110 |
| mcp-feedback | `report_feedback` tool + OTLP transport | fastmcp, mcp, httpx, pydantic | a2web | 0.3.0 | 2 | 238 |
| mcp-result-wire | FastMCP middlewares for page-tsv output | page-tsv (shelf), fastmcp, mcp | **none live**: a2kay use-case active, no pin, no import | 0.2.0 | 3 | 257 |
| mcp-steps | Gherkin harness that drives an MCP server | fastmcp, pytest-bdd (runtime) | a2kay (tests) | 0.1.0 | 6 | 146 |
| page-tsv | `Page[T]` + render by consumer | pydantic, lean-wire (shelf) | a2kay | 0.2.1 | 19 | 712 |
| partial-time | dates as intervals at their written precision | none | a2kay | 0.1.0 | 2 | 95 |
| path-pattern | brace path templates, both directions | none | a2kay | 0.1.0 | 8 | 154 |
| plugin-surface | declarative plugin manifest + loader | none | a2web; a2kay pins it with **no use-case** | 0.2.0 | 8 | 309 |
| process-lock | exclusive flock on a path | none | a2kay | 0.1.0 | 3 | 121 |
| record-mine | repeated-record region → markdown | lxml (medium) | a2web | 0.2.0 | 3 | 695 |
| settings-base | env/YAML plumbing under pydantic-settings | pydantic-settings (medium) | a2web | 0.1.0 | 3 | 107 |
| sqlite-resource | lazily opened aiosqlite connection | aiosqlite (light) | a2web | 0.1.0 | 2 | 118 |
| sqlite-sidecar | SQLite open, transaction and busy rules | none | a2kay | 0.2.0 | 14 | 314 |
| timefmt | adaptive duration formatter | none | a2web | 0.1.0 | 1 | 39 |
| verb-cli | pydantic signature → argparse flags | none | a2kay | 0.1.0 | 6 | 143 |
| yaml-merge | carry values into existing YAML, comments kept | ruamel.yaml (medium) | a2kay | 0.1.0 | 1 | 166 |

What the table shows:

- 22 of 50 packages have **no base runtime dependency**, and 33 export **six names or fewer**. For
  these, the per-package cost is the larger part of the package.
- Consumers lag behind and that is fine. a2web pins a2effect 0.1.0, async-scope 0.1.0,
  plugin-surface 0.1.0 and llm-wobble 0.4.0 while newer tags exist. With git tags, a consumer who
  does not move pays nothing. This matters for the "one version" cost in §4.
- `any-proc` (run/supervise) does not exist on the shelf. Only an a2kay supervisor bug refers to it.
  It cannot be grouped until it is promoted.

## 3. The grouping, with verdicts

Every candidate group was put through four checks, in this order. Any one of them can kill it.

1. **One subject?** It must be a noun a consumer would `import` cold, the way stdlib names `pathlib`,
   `zoneinfo` or `sqlite3`. "Touches FastMCP" is a stack, not a subject. "What a path and its bytes
   say" is a subject.
2. **Same dependency weight, or can the heavy part go behind an extra?** The base dependencies of a
   group are the union of its members' hard dependencies. A member that would force a heavy or
   compiled dependency on the rest goes behind an extra, or stays out.
3. **Closes an intra-shelf edge, or at least does not open one?**
4. **Same consumer set and cadence?** Matters a lot for heavy members and little for zero-dependency
   ones. A non-user of a module pays only when it re-pins to pick up something else.

### ✅ Do

| Group (import) | Members | Base deps / extras | Why it holds |
|---|---|---|---|
| **any-file** (`any_file`) — keeps the name | any-file, atomic-io, path-pattern, jsonl-log, managed-region (→ `any_file.region`) | anyascii | One subject: paths, names and bytes on disk, and writing to a file safely (atomically, by appending, or inside a block a machine co-owns with a person). a2kay only. Zero to light dependencies. Gives the atomic write a home that people find; today it exists 3 times. managed-region is marker-agnostic, so it belongs with file writes, not with markdown. |
| **any-time** (`any_time`) | partial-time, due-schedule, timefmt | croniter (light, hard) | A stdlib-shaped subject (dates, schedules, durations). No `[cron]` extra: `schedule_is_due` is one entry point that routes interval vs cron, so an extra would mean an import failing at first call, which rule 2 forbids. Splitting it into two functions to save a light pure-Python dependency is not worth it, so a2web inherits croniter. Consumers differ (timefmt is a2web's), but a bump costs a2web nothing until it chooses to move. |
| **any-proc** (`any_proc`) | process-lock, launchd-agent | none | One subject: a process's life on this machine (claim, start at login). Both a2kay, both dependency-free. The unpromoted run/supervise code joins it when promoted, rather than becoming a third package. `launchd_agent.testing` becomes `any_proc.testing`. |
| **any-mcp** (`any_mcp`) | mcp-arg-errors, mcp-bridge, mcp-clients, mcp-feedback, mcp-steps | fastmcp, mcp, httpx, pydantic; `[testing]` pytest-bdd (mcp-steps → `any_mcp.testing`) | It passes on dependency weight: a shared heavy dependency is the strongest reason to group, because one package means one fastmcp range. Today four manifests declare it as `>=3,<4` or `>=3.4,<4` independently. Subject: a FastMCP server's edges (arguments, transport, clients, feedback, tests). Weakness: a2web uses only feedback, so a fix to bridge does not concern it. That is accepted, because a2web already carries fastmcp. mcp-clients is dependency-free and pays for fastmcp it does not use; accepted, because its only consumer is an MCP server. |
| **any-sqlite** (`any_sqlite`) | sqlite-sidecar, fts-query, sqlite-resource | none; `[async]` aiosqlite | One engine, one subject. Synchronous and dependency-free in the base. The aiosqlite connection goes behind `[async]`, so the two models never share an import path by accident. The http-cache edge now points at `any-sqlite[async]`, which is no worse than today. |
| **lean-wire** (`lean_wire`) — keeps the name | lean-wire, page-tsv (→ `lean_wire.page`) | pydantic | Closes the edge that forced a2kay's same-tag workaround. Same dependency. a2web gains a module it does not import, at zero dependency cost. |
| **anyllm** (`anyllm`) — keeps the name | anyllm, llm-cache (→ `anyllm.cache`, `[cache]` aiosqlite), llm-wobble (→ `anyllm.wobble`) | none; `[cache]` plus the existing SDK extras | Closes the edge that stops a2web pinning anyllm. llm-wobble is dependency-free and both consumers use it next to anyllm. The base stays SDK-free. |
| **any-html** (`any_html`) | html-fragment, record-mine, json-in-html, dom-schema, content-extract | lxml, selectolax, trafilatura | One subject: what an HTML page says. a2web only, and a2web uses all five. The parsers are already in a2web's lock. Weakness: content-extract keeps its edge to convert-md (see §5). |
| **any-http** (`any_http`) | http-fetch, http-cache, browser-cookies | curl_cffi; `[cookies]` browser-cookie3 | One subject: fetching over HTTP as a browser would. a2web only. Edge to `any-sqlite[async]`, the same as today's edge to sqlite-resource. |
| **any-yaml** (`any_yaml`) | yaml-merge, any-frontmatter (→ `any_yaml.frontmatter`) | ruamel.yaml | Closes the any-frontmatter → yaml-merge edge, which today hides behind an extra precisely so that "a consumer that pins yaml-merge itself is not handed a second source". Same dependency, same consumer. Frontmatter is YAML that happens to sit in a markdown file, and its dependency is ruamel, not markdown-it. |

### ❌ Keep separate

| Package | Why grouping fails |
|---|---|
| **anyembed** | torch + transformers. In an "LLM family" with anyllm, every anyllm consumer would download about 2 GB, or anyllm would turn into a set of extras with nothing in it. A different consumer set (a2kay only), and a different subject (vectors, not completions). |
| **any-browser** | Engine extras with browser binaries and its own test lane (`make test-browser`). It already is a domain package. |
| **convert-md** | The fastest-churning package on the shelf (0.10.0), with the heaviest extras (`[pdf]`, `[documents]`). Fusing it into any-html or any-file would push its cadence onto every member, and a minor bump in a group package would happen almost weekly. |
| **git-porcelain** | Already a domain (38 names, a `testing` module). Nothing to absorb. |
| **bdd-tags** | It is a `pytest11` entry-point plugin that is "on once installed". Inside any group, installing the group switches the plugin on for every consumer's test run. Plugins stay alone. |
| **a2effect**, **async-scope**, **plugin-surface** | Cross-cutting: every group may want them. Folding them into one group would create the edges this document removes. |
| **dir-trust** | A trust policy, not a YAML or file helper. It uses ruamel only for its grant store. As part of any-yaml it would be a second subject, and the kitchen sink of RECONCILE step 2. |
| **any-markdown**, **event-bus**, **verb-cli**, **settings-base**, **asgi-token-gate**, **json-match** | No sibling with the same subject today (managed-region looked like one for any-markdown, but it is marker-agnostic and went to any-file). A 1-member "group" is just a rename that costs churn. |
| **duckdb-sidecar**, **mcp-result-wire** | **Do not migrate dead weight.** Each has an active a2kay use-case but no pin and no import. Run RECONCILE step 4 (deprecate) first. If mcp-result-wire comes back, it belongs with lean-wire's `page` module (its edge), not in any-mcp. |

### Later (named trigger)

- **any-proc run/supervise:** joins any-proc when the code is promoted. Not before; the shelf
  never builds on spec.
- **any-asgi** (asgi-token-gate + async-scope's `[asgi]` lane): when a second ASGI helper is
  promoted.
- **any-test** (json-match + the non-plugin half of bdd-tags): when a second consumer adopts
  json-match. Today it is a2kay test code with one import.
- **dir-trust imports `any_file.atomic`** (it stays its own package): when a repo-wide snapshot tag exists (§5). Then it can import
  `any_file.atomic` instead of keeping its private copy.

## 4. Rules for a grouped package

1. **Admission.** A module joins a group only if it passes all four checks in §3. Size is never
   the reason: a 3-line function is welcome, and a module with heavy dependencies is not, whatever
   its size.
2. **Layout.** One submodule per former package (`any_time/partial.py`, `any_time/schedule.py`,
   `any_time/fmt.py`). Public names stay as they were.
   - The top-level `__init__` re-exports **every member not behind an extra**. Then
     `from any_time import format_duration` works with the base install.
   - A module behind an extra is imported only by its own path (`from any_sqlite.aio import …`). It
     raises an `ImportError` naming the extra (`pip install any-sqlite[async]`) at import time,
     never at first call.
   - The package never imports a module behind an extra from its own `__init__`.
3. **Extras.** An extra is named after the capability, not the library (`[cron]`, `[async]`,
   `[cache]`, `[cookies]`, `[testing]`). Rule 0008 applies to extras too. An extra may never
   contain a shelf package: that is how the yaml-merge collision started.
4. **One version per package.**
   - A release bumps the whole package: additive in any module → minor, breaking in any module →
     major (resolution 0007, monotonic contracts).
   - What a bump costs consumers: nothing until they re-pin. When they do re-pin to get a fix in
     module A, they also take module B's additive changes, and monotonic contracts make that safe.
     A breaking change anywhere becomes a major for every consumer of the group. That is the real
     price, and it is intended pressure: break less.
   - Tags stay `<package>-vX.Y.Z`. A per-module changelog section in the package README records
     which module moved.
5. **`testing`.** One `<pkg>.testing` module (a subpackage when two members bring doubles). pytest
   and pytest-bdd are only behind `[testing]`, and the package itself never imports `testing`. This
   is the a2effect pattern, today the only package that declares the extra. No `pytest11` entry
   points in a group (bdd-tags).
6. **What stays out:**
   - a different dependency class (heavy or compiled while the rest is pure)
   - a different release cadence (convert-md)
   - a plugin activated by installation
   - a cross-cutting primitive every group would want
   - a member whose only link is "same stack".

   A different consumer set alone does not exclude a dependency-free member. Combined with a heavy
   dependency, it does.
7. **Catalog and use-cases.**
   - One `catalog/<pkg>.toml` per package, with a `[modules]` table: one line of capability per
     module, which keeps the cold-reading test of resolution 0008 working at module level.
   - One `use-cases/<consumer>--<pkg>.toml` per consumer, with a `modules = [...]` list of what it
     imports. Without that list, Article VIII's orphan check goes blind inside a group: a dead
     module would live forever because a sibling is used.
   - RECONCILE step 4 becomes per module: an unused module is deprecated in a minor and removed in
     the next major.
8. **Naming.** `any-<domain>`. The import name never shadows the stdlib or a common library, so no
   `time`, `files`, `json`, `html`, `yaml` or `sqlite`. The `any_` prefix guarantees this. Where a
   member already carries a name that passes resolution 0008 (any-file, any-markdown, anyllm,
   lean-wire), the group **keeps that name**. Consumers who already pin it then bump a tag instead
   of rewriting a line.

## 5. Migration

### Shims: ❌ retire at once

Tags are permanent repo-wide snapshots (resolution 0001). A consumer still pinned to
`partial-time-v0.1.0` keeps working forever at zero cost, so a re-export shim adds nothing. It is
also harmful: a shim is a **new** tag of the old name that depends on the group. That creates a
second URL for the group, which is the transitive collision a2kay's and a2web's comments describe.
So:

- The old directory leaves `main` in the same commit that tags the group.
- The old manifest gets `status = "deprecated"` and lineage `absorbed-into = "<group>"` (glossary
  arc).
- Old tags are never deleted.

### Per group, shelf side

The steps are the same every time:

1. Move `src/<old>/` to `src/<group>/<module>.py` (or a subpackage) and move the tests under
   `tests/<module>/`.
2. Merge the dependencies and extras into one `pyproject.toml`.
3. Fix the root `pyproject.toml`: the workspace sources and the dev group (e.g.
   `any-frontmatter[merge]` → `any-yaml`).
4. Write the group manifest with `[modules]`, deprecate the old manifests, and rewrite the
   use-cases with `modules = [...]`.
5. Add one ledger `verdict` row per absorbed package (RECONCILE closes the loop).
6. Run `make catalog` and `make check`, then tag.

### Per group, consumer side

1. In `dependencies` and `[tool.uv.sources]`: N lines out, one in, with extras.
2. Rewrite the imports, mechanically:
   - `from partial_time import X` → `from any_time import X`
   - `from launchd_agent.testing import …` → `from any_proc.testing import …`
3. Fix deptry and import-linter names, if they are listed.
4. Run `uv lock` and `make check`.

### Effort and order

Effort comes from the consumer import counts (a2kay + a2web source and tests) and the shelf-side
steps. XS < 1 h, S ≈ half a day, M ≈ a day.

| # | Step | Removes | Consumer import sites | Effort |
|---|---|---|---|---|
| 0 | RECONCILE: deprecate duckdb-sidecar, mcp-result-wire; add a2kay's missing plugin-surface use-case | dead weight, an unrecorded consumer | 0 | XS |
| 1 | **lean-wire ⊃ page-tsv** | a2kay's same-tag workaround | a2kay 5 | XS |
| 2 | **anyllm ⊃ llm-cache, llm-wobble** | a2web's unpinnable anyllm (check that the root workspace's anyllm source no longer leaks once the edge is gone) | a2web 7, a2kay 1 | S |
| 3 | **any-file ⊃ atomic-io, path-pattern, jsonl-log, managed-region** | atomic-write home | a2kay 9 | S |
| 4 | **any-time** | — | a2kay 6, a2web 2 | S |
| 5 | **any-proc** | — | a2kay 6 | XS |
| 6 | **any-yaml** | the `[merge]` extra hack | a2kay 8 | S |
| 7 | **any-mcp** | four separate fastmcp ranges | a2kay 5, a2web 1 | S–M |
| 8 | **any-sqlite** | — | a2kay 12, a2web 1 (+ http-cache inside the shelf) | M |
| 9 | **any-http** (after 8: depends on `any-sqlite[async]`) | — | a2web 29 | M |
| 10 | **any-html** | — | a2web 51 | M |

Why this order: steps 1 and 2 remove hazards the consumers documented, so they pay off first.
Steps 3–6 are a2kay-only or nearly so, and dependency-free, which makes them the cheapest proof of
the rules.

**a2web moves once, at the end.** Steps 2, 4, 7, 8, 9 and 10 all produce tags a2web could take. It
does not take them one by one. It stays on its current tags (old tags never break) and re-pins
everything in one session after step 10. The a2web import counts above are what that one session
rewrites, about 91 sites. a2kay follows each step as it lands, because the hazard it documented is
removed in step 1. Total: about 6–7 working days.

### Preconditions (check before step 1)

- `tests/test_boundary.py`, `tools/arch_rules.py` (Rego) and the `Makefile` per-package loop
  (`for p in packages/*/`) were not read for this research. Verify that none assumes one import name
  per `packages/*` directory, or one module per package.
- The derived catalog (`tools/catalog.py`) must render the `[modules]` table, or the findability gain
  never reaches the reader.

### Doctrine changes that ship with step 1

- `docs/agent-loop.md` `PROMOTE` step 3 gains a sub-step **before** "mint `packages/<name>/`":
  *does a group already own this subject? Then add a module and bump its minor.* This is the change
  that actually alters behaviour; the rest is bookkeeping.
- `RECONCILE` step 4 becomes per module (rule 7), and step 2 (kitchen sink) names the four admission
  checks.
- A resolution records the admission checks, the no-shim decision and the catalog rule for groups:
  `kind` = the strongest member kind (`any-*` over `primitive`), `tier` = the highest member tier.

### Out of scope, but the bigger lever

Grouping removes the edges **inside** a group. The edges **between** groups stay:
any-html → convert-md, any-http → any-sqlite, and any future any-yaml → any-file. Each still
forces a consumer to pin both at one snapshot.

The root fix is a **repo-wide release tag** (`shelf-v2026.10.10`) that a consumer pins for every
shelf package at once. Tags are already snapshots of the whole repo, so only the name and the
discipline are missing. With it, cross-group edges cost nothing, and dir-trust and any-yaml can
import `any_file.atomic` instead of keeping private copies. Until then, the rule holds: **a private
copy of fewer than about 20 lines beats a cross-group edge.**

## 6. Count

```
before                             50 packages
  33 absorbed into 10 groups      -23
after grouping                     27   (10 groups + 17 unchanged)
  deprecate duckdb-sidecar,
  mcp-result-wire (step 0)         -2
after RECONCILE                    25
```

The 17 unchanged packages: a2effect, any-browser, any-markdown, anyembed, asgi-token-gate, async-scope,
bdd-tags, convert-md, dir-trust, duckdb-sidecar, event-bus, git-porcelain, json-match,
mcp-result-wire, plugin-surface, settings-base, verb-cli.

## 7. How this fails

- **A group becomes `utils`.** Guard: the cold-reading test from resolution 0008 is run on the group
  name **and** on every module line in `[modules]`. A module that fails it goes back out.
- **Module-level rot hidden by a used sibling.** Guard: `modules = [...]` in use-cases, and per-module
  RECONCILE (rule 7). Without both, grouping quietly turns off Article VIII.
- **Breaking-change blast radius.** A major in any-mcp touches a2web for a bridge change it does not
  use. Accepted. If it happens twice in a TTL window, split the member out again; splitting is a
  RECONCILE verb.
- **Promotion friction moves instead of disappearing.** Today it is "mint a package". After this
  change it is "find the right group and bump its version". This is cheaper only if new helpers
  actually land in groups. Measure it: the next five promotions, counted by how many minted a new
  package.
