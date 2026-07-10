## Why

`convert-md`'s `.docx` chain is `[PandocEngine, MarkitdownEngine]` — pandoc
primary, markitdown fallback. That choice was **inherited verbatim from R142**
(the original markdown-conversion-engines research) on a single reasoned claim:
pandoc's `--track-changes=all` preserves tracked-changes/redline metadata that
markitdown's plain-text extraction can't replicate. It was never benched.

The whole `pdf-engine-verification` change (archived) built a real, re-runnable
bench and overturned the inherited PDF choice (docling → dropped entirely) on
evidence. The docx choice has had none of that scrutiny, yet it carries the
heaviest dependency in the `documents` extra: `pypandoc-binary` bundles a
~100MB+ pandoc executable, pulled in **solely** for that one flag.

Two things make the inherited justification suspect on inspection, before any
bench runs:

1. **`--track-changes=all` is probably the wrong behavior for the live
   consumer.** a2kay ingests heterogeneous documents into a vault as markdown
   (`use-cases/a2kay--convert-md.toml`). Tracked changes in a `.docx` are not
   version history — they're *un-accepted pending redlines* sitting in one
   file. `--track-changes=all` renders both the inserted and deleted text as
   inline markup, i.e. it injects redline garbage into the vault. The clean
   final text — what a knowledge base actually wants — is what pandoc's
   *default* (`--track-changes=accept`) and markitdown/mammoth already produce.
   The one capability justifying pandoc-primary is, for this use case, a
   liability, not an asset.
2. **markitdown-for-docx *is* mammoth with a wrapper.** markitdown pulls
   `mammoth~=1.11.0` under its `docx` extra and routes docx→HTML→markdown
   through it. mammoth's own dependency footprint is a single tiny library
   (`cobble`). So a docx path via mammoth (either through markitdown, or raw
   mammoth → `convert-md`'s *existing* trafilatura/html2text HTML chain) is
   near-weightless and reuses substrate the base install already carries.

Because docx is a **semantic** format (structured OOXML), not a lossy layout
format like PDF, the engines should *converge* on the easy 90% (headings,
tables, footnotes, lists, images) and diverge only at capability edges
(tracked changes, OMML equations, embedded-image handling). The bench must be
built to expose exactly those edges — which changes its shape versus the PDF
bench (see design.md D2).

## What Changes

- **Extend the bench harness to docx.** It is PDF-hardcoded today
  (`run_bench.py` globs `corpus/*.pdf`, iterates 5 PDF engines). Add a docx
  capability-grid: a `.docx` corpus, docx engine runners, per-capability
  scoring — reusing the existing isolated-install + model-free-fidelity-grade
  machinery, not a parallel one.
- **Synthesize per-capability docx fixtures** (design.md D2): one authored
  `.docx` per capability so a failure attributes to exactly one feature. docx
  is semantic, so synthesis is *more* correct here than downloading real files
  (the inverse of the PDF corpus's real-document bias — see design.md D2). The
  user's own docx are used only to discover which capabilities matter and to
  sanity-check grades; they are **never committed** (design.md D2, privacy
  boundary carried over from the PDF corpus's "never the user's own docs").
- **Run three engines** — pandoc (accept-mode *and* all-mode, to quantify the
  redline behavior), markitdown, and raw mammoth → HTML chain — score, decide.
- **Decide** from evidence: single engine, or the tiered shape below (leading
  hypothesis, not foregone): a light default (mammoth/markitdown) for the
  common grid + pandoc behind an opt-in extra for consumers that genuinely
  want redline preservation + graceful degradation when the heavy engine is
  absent (`lost=["tracked_changes"]`, never an ImportError — same contract the
  PDF chain already honors).

### Two shelf primitives extracted from doing this (not invented ahead of it)

- **`generic-first, specific-second`** — a governance resolution + distillation
  into `agent-loop.md`: an agent reasons about a shelf package's capability
  *generically first* (what does "convert docx" need at large), then uses the
  live consumer only to *weight* which capabilities are common (→ light
  default) vs rare (→ opt-in / graceful-degrade). This change is the worked
  example. Ready to write now (design.md D5).
- **`WORKFLOW: BENCH`** — the shelf now has two instances of the same exercise
  (PDF done, docx here): isolated-capability corpus → transient per-engine
  installs → model-free fidelity grade → dated evidence doc → evidence-backed
  build-vs-adopt decision → ledger row. Extract it as a named workflow in
  `agent-loop.md` so the next engine/tool comparison reuses the method instead
  of re-deriving it. **Extracted from this run, finalized as it confirms the
  pattern generalizes** (design.md D6) — deliberately not written before the
  second instance exists.

## Capabilities

### New Capabilities
- `docx-engine-comparison`: a maintained, re-runnable capability-grid benchmark
  comparing docx→markdown engines, independent of any one consumer's opinion.
- `bench-workflow`: `WORKFLOW: BENCH` in `agent-loop.md` — the reusable
  evidence-backed tool-comparison method, generalized from the PDF and docx
  benches.

### Modified Capabilities
- `convert-md` (docx path): engine selection becomes evidence-backed; likely a
  lighter default + optional pandoc tier, with `pypandoc-binary` dropped from
  the mandatory `documents` extra if the evidence supports it.
- `agent-loop` (package-reasoning discipline): gains the generic-first /
  specific-second rule agents apply when shaping any shelf package.

## Impact

- **Consumer-facing:** if pandoc is dropped from the mandatory `documents`
  extra, that removes a ~100MB+ binary from every `convert-md[documents]`
  install. If tiered, a redline-dependent consumer opts into a new extra — no
  silent behavior loss (graceful degradation + fidelity grade). Either way it
  re-cuts a `convert-md` version; a2kay repoints on its own cadence (RECEIVE).
- **No live consumer is known to depend on tracked-changes preservation** —
  a2kay's is the only active docx use-case and it wants clean vault text. So
  the expected direction is "drop pandoc-primary," but that is the bench's
  verdict to reach, not this proposal's to assume.
- **Scope discipline:** shelf-side only. Running a2kay's real corpus through
  the new path (round-trip verification) is a2kay's own follow-up, not part of
  this change — mirrors how `pdf-engine-verification` left a2web's plumbing to
  a2web.
