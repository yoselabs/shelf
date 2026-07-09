## Context

`convert-md`'s `documents` extra bundles `docling` (PDF), `pypandoc-binary`
(docx), and `markitdown` (pptx/xlsx — its strongest formats). The split into
a separate package/extra away from `convert-md` base was to contain a version
conflict discovered while adopting `content-extract` into `a2web`: the shared
`shelf-a2web` workspace lock couldn't satisfy both docling's stack and
`a2kit`'s `typer` floor simultaneously.

That fix was never re-verified against docling's current release, and the
PDF-engine choice itself was never comparison-tested — both were reasoned
decisions, not evidence-backed ones (per the micro-software skill's
distinction: flag reasoned-not-verified separately from verified).

## Decisions

### D1 — The typer conflict is real, current, and structural (verified 2026-07-09)

Checked live against PyPI, not memory:

- `docling` 2.111.0 is now a thin shim depending on `docling-slim[standard]`.
- `docling-slim` 2.111.0's **unconditional base** dependency is
  `docling-core<3.0.0,>=2.86.0` (not extra-gated).
- `docling-core` 2.86.0's **unconditional base** dependency is
  `typer<0.25.0,>=0.12.5` — also not extra-gated.
- a2web currently resolves `typer==0.25.1` (from `a2kit`).

Empirical confirmation — `uv add "typer>=0.25" "docling-slim[cli]"` in a
throwaway project — fails resolution with exactly this chain:

```
docling-core==2.86.0 depends on typer>=0.12.5,<0.25.0
docling-slim depends on docling-core (unconditional)
project depends on typer>=0.25 AND docling-slim[cli]
→ unsatisfiable
```

**This is stronger than the original diagnosis assumed.** The earlier
reasoning treated the conflict as living in an *optional* extra (`cli`/`all`)
— implying "don't request the extra" would dodge it. It doesn't: the
`typer<0.25` pin comes from `docling-core`, which is a **hard, unconditional**
dependency of `docling-slim` at every install, extras or not. There is no way
to install *any* part of docling without inheriting `typer<0.25`.

Consequence for the shelf's separate-package containment fix: it still works
(it keeps the pin out of any lock that doesn't explicitly depend on the
document-engines package), but "just skip the extra" was never actually the
mechanism keeping a2web safe — a2web is safe because it doesn't depend on the
document-engines package **at all**, full stop, not because it's selectively
avoiding one extra within a shared package.

### D2 — Comparison harness scope (draft — refine in tasks.md)

Corpus: public-domain PDFs only (never the user's own documents), spanning:
- a text-heavy article/report (baseline prose + headings)
- a table-heavy document (financial report, spec sheet)
- a multi-column layout (academic paper)
- a scanned/OCR page (image-only PDF)

Engines to compare (revised 2026-07-09 after a landscape survey — see
Appendix: Candidate Survey below):

- **`docling`** — fidelity ceiling / control, even though it's excluded for
  a2web-shaped consumers per D3. Establishes what "best case" looks like.
- **`pymupdf4llm`** — cleanest dependency profile of any candidate (no
  ML/GPU, AGPL but no reported conflicts); real chance of "good enough" for
  a2web's actual named use case (prose-heavy regulatory filings / manuals),
  not just academic table-heavy papers.
- **`markitdown`** — already installed in this repo (0.1.6), zero extra
  cost to test, R142 already trusts it for pptx/xlsx; worth knowing
  definitively whether its PDF path is disqualifying-bad or just mediocre.
- **`marker`** — stretch/optional only, run last, only if the above three
  all fail the OCR/scanned-page axis. GPL-3.0 (the other three are all
  permissive — a real adoption question if it ever won), GPU-preferred
  (doesn't fit a serverless/CLI fetcher shape), and has active Python-3.14
  breakage in its own tracker (pydantic + Pillow/surya-ocr pins) as of this
  survey — check live before running, same method as D1.

Dropped from the run entirely: `pdfplumber` — a build-your-own-extraction
primitive, not a comparable "convert and done" engine, testing something
different in kind than the others.

`unstructured` is reinstated as a **probe candidate** (revised after D4
below removed the reason it was dropped): it's run through the same
isolated-install mechanism as every other engine, so its extras-heavy shape
no longer risks a shared-lock conflict — there's no shared lock. It's simply
not a candidate for becoming convert-md's actual runtime dependency without
its own separate justification later.

Scoring axes (qualitative rubric, not a single score):
- table structure preserved (rows/cols, not flattened prose)
- heading hierarchy recovered
- reading order correct on multi-column pages
- OCR/scanned-page handling
- noise (headers/footers/page-number leakage)

### D3 — Decision rule

Docling only earns its `typer<0.25` tax if it clears the alternatives by a
margin on the axes above — not just "reputationally the leader." If an
alternative is close enough and conflict-free, prefer it; the tax is real and
permanent for every future consumer of the documents package.

**Tightened (2026-07-09, a2web merge) — conflict-free is a hard filter, not a
tiebreaker, for any consumer shaped like a2web.** a2web resolves
`typer==0.25.1` via `a2kit`; `docling-core`'s `typer<0.25` pin is unconditional
(D1). That means "docling wins on fidelity but loses on tax" isn't a judgment
call a2web can make differently — it's simply uninstallable there. So the rule
splits by consumer shape:

- For a consumer that can absorb the tax (no competing `typer>=0.25` pin):
  fidelity margin still governs, tax-adjusted, as originally written.
- For a consumer pinned like a2web: docling is excluded from consideration
  outright regardless of fidelity score; the winner is the best-scoring
  candidate *among the conflict-free set*.

a2web is the concrete instance of the second case today and the reason this
change stopped being hypothetical.

### D4 — Harness lives inside `convert-md`; every engine is a transient, isolated probe install (decided 2026-07-09)

**Location:** the harness lives inside `packages/convert-md/` itself (e.g.
`packages/convert-md/bench/`), not a standalone `tools/pdf-bench/`. Rationale:
`convert-md` is the package that actually produces `content_md` — it's the
project this decision belongs to, self-contained. If the shelf decomposes
further later, the harness and its retained results travel with the package
that owns the PDF-engine decision, rather than living somewhere that has to
be rediscovered or re-linked. This resolves the location question the
earlier Open Questions entry left unresolved — superseding the "lean toward
standalone `tools/`" lean below (see Non-Goals note — that lean is now
wrong and is corrected here, not deleted, so the reasoning trail stays
legible).

**Installation strategy — no engine becomes a real `convert-md` dependency
via the harness, not even `unstructured` or `marker`.** Every compared
engine (docling, pymupdf4llm, markitdown, marker, unstructured — and
pdfplumber if it's ever reinstated) is installed transiently and in
isolation per-engine at bench-run time (e.g. `uv run --with <engine>` against
a per-engine ephemeral environment, one engine per subprocess), never added
to `convert-md`'s `pyproject.toml`, not even behind the `documents` extra.
Consequences:

- **The D2/tasks.md-2.2 pruning step is retired.** The original concern
  ("prune candidates that themselves drag in unresolvable conflicts") assumed
  candidates needed to co-resolve in one shared lock to be compared. They
  don't — isolation means docling's `typer<0.25` and any future marker/
  unstructured pin never have to coexist. Nothing needs pruning for conflict
  reasons anymore, only for practicality (license, weight, GPU shape) —
  which is why `marker` is still stretch/last-run and `pdfplumber` is still
  dropped, but for those reasons, not resolution-failure reasons.
- **`marker`:** probe it too, via the same isolated mechanism — check
  live (same method as D1) whether a minimal/CPU-only install composition
  exists (e.g. a slim extra that skips the full Surya-OCR/GPU stack) before
  defaulting to its heaviest form; if no minimal composition exists, still
  run it in isolation and just record the weight in the results, since
  isolation means that weight never touches `convert-md`'s real dependency
  graph regardless.
- **`unstructured`:** same treatment — probed, never installed as a primary
  dependency, no separate conflict investigation required first (see D2
  revision above).

**Persistence:** results are committed as artifacts inside the package
(e.g. `packages/convert-md/bench/results/<date>.md` or `.json`), not
regenerated-only. The harness is re-runnable but not required to run on
every `make check` — occasional reruns (new corpus PDF, new engine version,
periodic re-verification) are the expected cadence, and the committed
results are what "docling is evidence-backed, not assumed" (the original
proposal's goal) actually means in practice: an inspectable, dated record,
not a claim that has to be re-derived from scratch each time someone asks.

### D5 — Drop docling entirely; `.pdf` becomes pymupdf4llm-only (decided 2026-07-09)

**This supersedes D3's "docling kept as fallback" outcome and v0.4.0's
`[PymupdfLlmEngine, DoclingEngine]` chain.** Recorded here, not just in the
ledger, because the ask driving this decision was explicit: track the
reasons, not just the typer conflict, so the choice is recoverable later
without re-deriving it. Full candidate set considered (not just the two in
the final chain): docling, pymupdf4llm, markitdown, marker, unstructured —
see the Appendix survey below and `bench/results/2026-07-09-findings.md` for
the complete evidence trail.

**Primary reason — semantic re-analysis, not typer.** Every prior scoring
pass (D2's axes, the CJK/math/infographic addendum) graded *visual/structural*
fidelity: markdown table syntax, heading nesting, reading order as rendered.
Re-scored instead for what an LLM consumer actually needs — can the facts,
values, and relationships be recovered regardless of formatting ugliness —
and the picture changes:

- **docling drops 100% of formulas** on math-heavy content
  (`<!-- formula-not-decoded -->` x8, `bench/outputs/docling__math_heavy.md`)
  — total, unrecoverable content loss. No surrounding-prose fallback, no
  partial structure — the content is simply gone.
- **pymupdf4llm's defects downgrade to cosmetic under this lens.** Its
  "broken" financial table (`pymupdf4llm__investor_infographics.md:295-320`)
  is ugly but every value stays attributable to the correct row/year — a
  reader (human or LLM) parses it correctly despite the formatting. Its CJK
  glyph-ID garbage is 100% confined to decorative icon legends, never real
  body prose (verified directly, both `ja_service_manual.pdf` and
  `zh_service_manual.pdf`). Its math-matrix stacking is odd-looking but every
  entry is present in correct order — reconstructable, not lost.
- **markitdown, the other live candidate, has two real semantic failures**
  under this same lens (not just docling's problem): `table_heavy.pdf`'s
  two-column reading order gets genuinely fused mid-sentence into
  wrong-seeming meaning (`markitdown__table_heavy.md:6-12`), and
  `math_heavy.pdf` doesn't just lose spacing — it severs a specific numeric
  claim (Archimedes' π bounds, `223/71 < π < 22/7`) from its own denominators
  across two disconnected locations (`markitdown__math_heavy.md:37-38`). Ruled
  out as "the answer for everything" on this evidence — it loses to
  pymupdf4llm on the exact axes (reading order, math) that matter most to an
  LLM reader.

Net: among the two candidates left standing after D3 (pymupdf4llm,
docling-as-fallback), **docling is the one with an actual unrecoverable
semantic failure mode (total formula loss); pymupdf4llm's failures are all
cosmetic once graded on meaning instead of shape.** Keeping docling as a
fallback bought nothing on this evidence — no corpus file in the full 8-file
run needed docling to recover content pymupdf4llm couldn't already deliver
(the original 4-category corpus found them tied; the extended corpus found
pymupdf4llm ahead or even).

**Secondary reason — the typer conflict, already established (D1/D3).**
Removing docling from `convert-md[documents]` entirely also means the
`typer<0.25` pin (D1) no longer exists anywhere in the package's dependency
graph, for any consumer, not just a2web-shaped ones. This was sufficient on
its own to justify demoting docling from primary in D3, but is explicitly
**not** the primary reason for removing it outright — the semantic evidence
above is. Recording both, and their relative weight, is the point of this
section: a future reader should not conclude "we dropped docling because of
a dependency conflict" when the deciding evidence was a content-loss finding
that would have justified the same removal even in a conflict-free world.

**Not promoted in its place:** neither markitdown (real semantic failures
above) nor marker (the one engine that renders math correctly, but still
disqualified on GPL-3.0 license + >30x CPU-only runtime — unchanged from the
marker addendum, cost/license grounds are orthogonal to this fidelity
finding). `.pdf` becomes single-engine: `[PymupdfLlmEngine]`, no fallback.
If a corpus is ever found where pymupdf4llm fails outright (not just
cosmetically), that's new evidence for a future decision, not something this
one guesses at.

## Non-Goals

- Not re-opening the reuse-vs-simplification doctrine question (settled:
  the shelf promotes speculatively, per resolution 0006, global-inventory
  reading).
- ~~Not deciding today whether to replace docling — that's the harness's
  job.~~ **Superseded by D5**: the harness did its job: docling is dropped
  entirely, not just demoted, per D5's semantic-recoverability evidence.

## Open Questions

- ~~Where does the harness live permanently~~ — **resolved by D4**: inside
  `packages/convert-md/`, engines installed as isolated transient probes,
  never as real package dependencies. (The `tools/pdf-bench/` standalone
  lean noted here originally is superseded — kept struck-through, not
  deleted, so the reasoning trail is legible.)
- `marker`'s GPL-3.0 license is a first-time question for this repo's
  document engines (docling/pymupdf4llm/markitdown are all permissive) —
  softened by D4: isolation means marker never becomes a real dependency
  just by being probed, so the licensing conversation only actually triggers
  if a future change proposes making it convert-md's *runtime* engine, not
  at harness-build time. Not blocking today.

## Appendix: Candidate Survey (2026-07-09)

A landscape survey (WebSearch + PyPI metadata, not exhaustive) ahead of
building the harness, to avoid guessing the D2 candidate list:

| Library | License | Weight | PDF fidelity reputation | Conflict risk |
|---|---|---|---|---|
| docling | MIT | Heavy (ML models, TableFormer) | Best table structure in surveyed benchmarks (~88% F1), strong hierarchy | Confirmed unconditional `typer<0.25` (D1) |
| marker (`marker-pdf`) | GPL-3.0 | Heaviest (Surya OCR, GPU-preferred) | "Safest single-tool default" per multiple 2026 benchmarks; 5-10x slower without GPU | Active Python-3.14 breakage (pydantic + Pillow/surya-ocr pins), per its own issue tracker as of this survey |
| pymupdf4llm | AGPL-3.0 (via PyMuPDF) | Lightest, no ML/GPU | Fast; weak on tables (widely reported not close to source) | None reported |
| markitdown | MIT | Light-medium (already installed, 0.1.6) | XML-parsing not ML, fast; tables "mostly plain text, complex styles lost"; strong consensus for pptx/xlsx (matches R142), weak-reputed for PDF specifically | None flagged; not deeply verified since it's already a dependency here |
| pdfplumber | MIT | Light, no ML | Good when you write custom table-extraction logic; not drop-in "convert and done" | None reported |
| unstructured | Apache-2.0 | Heavy, many optional extras | General-purpose; historically middling table fidelity vs specialists | Not deeply checked — extras-heavy shape resembles what caused the docling conflict |

Sources are 2026 benchmark blogs (themenonlab, pdfmux, bswen, file2markdown,
danilchenko.dev) and marker's own GitHub issues — no independent community
forum (Reddit/HN) sentiment surfaced beyond these; treat the specific F1/speed
numbers as directional, not gospel. **The harness itself, run against this
repo's own corpus, is the real evidence source** — this survey only scopes
which candidates are worth that investment.
