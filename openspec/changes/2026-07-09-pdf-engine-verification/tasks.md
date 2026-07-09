## 1. Conflict verification (done)

- [x] 1.1 Check docling/docling-slim/docling-core PyPI metadata live
- [x] 1.2 Empirically confirm the conflict via `uv add` in a throwaway project
- [x] 1.3 Document the exact dependency chain in design.md D1

## 2. Comparison harness

- [x] 2.1 Assemble public-domain PDF corpus (4 categories: prose, table-heavy,
      multi-column, scanned/OCR) — cite source of each PDF (e.g. arXiv,
      gutenberg, gov publication). Done with one documented deviation: 2 of 4
      are arXiv (not strict public domain) — see `bench/corpus/README.md`
      "Deviation" note.
- [x] 2.2 Build the harness inside `packages/convert-md/bench/` (D4); each
      engine runs as a transient, isolated per-engine install (`uv run
      --with <engine>`) except docling/markitdown which are already real
      `documents`-extra dependencies. Hit and fixed a real platform bug along
      the way (docling MPS/float64 crash on Apple Silicon — see results.md).
- [x] 2.3 Write the harness: run each engine over each PDF, capture output.
      docling, pymupdf4llm, markitdown, unstructured all ran clean (16/16
      cells). marker run separately — CPU-only, 3/4 cells ok (1 transient
      crash), 15-60x slower than docling/pymupdf4llm, competitive fidelity
      but doesn't change the decision (see results.md marker addendum).
      Corpus later extended with 4 files (CJK ja/zh service manuals,
      math-heavy arXiv paper, infographic-dense investor report; all 20
      cells across all 5 engines ran clean) — headline finding: math-heavy
      PDFs are an open gap (docling drops all formulas, pymupdf4llm partial
      loss on display equations, only marker renders correct LaTeX); CJK has
      real but non-fatal defects in pymupdf4llm/markitdown (vertical-text
      fragmentation, glyph-ID leakage) that docling/marker avoid. Infographic
      PDF re-trimmed to actual chart/table-dense pages and re-run: all
      engines retain the financial table's *data*, but structure quality
      diverges sharply — marker renders it as a perfect table, markitdown as
      clean linear text, pymupdf4llm/docling both corrupt the table
      structure (duplicated headers, jammed rows), unstructured destroys it
      entirely (one value per line, no row/column association); docling and
      marker both silently drop the History timeline's text as an image
      placeholder, pymupdf4llm/markitdown/unstructured do not.
      See results.md "Extended corpus addendum".
- [x] 2.4 Score each output against the D2 fidelity axes — human-judged
      (direct reading of outputs), not LLM-judged; rubric + evidence in
      `bench/results/2026-07-09-findings.md`.
- [x] 2.5 Commit results as artifacts under `packages/convert-md/bench/results/`
      (D4 persistence) — `2026-07-09-findings.md` committed.
- [x] 2.6 Write up findings: docling and pymupdf4llm both clearly outscore
      markitdown and unstructured on reading-order/heading/table structure
      on this corpus. Per D3, pymupdf4llm is the conflict-free candidate that
      actually unblocks a2web; docling remains the fidelity ceiling only for
      consumers that can absorb the tax. Full writeup in results.md.

## 3. Decide and apply

- [x] 3.1 Decision: **replace** (primary only — docling kept as fallback, not
      dropped). No clear fidelity margin for docling over pymupdf4llm on this
      corpus, so per D3 the tax isn't earned. Recorded as ledger entry
      `ledger/0034-convert-md-pdf-engine-swap.toml`.
- [x] 3.2 Swapped: `dispatch.py`'s `.pdf` chain is now `[PymupdfLlmEngine,
      DoclingEngine]`; new `convert-md[pdf]` extra (pymupdf4llm only, no
      docling/typer conflict); `[documents]` keeps docling as PDF fallback.
      Re-cut convert-md-v0.4.0. `make check` green (309 passed, 86.59% cov,
      lint/type/spell/deps clean). **Round-trip through a2web NOT done here**
      — out of this change's scope (shelf-side only per proposal.md Impact);
      a2web's own follow-up (BACKLOG.md, superseded PDF-tier item) picks up
      `convert-md[pdf]` when it builds its Tier 4 routing/plumbing.
- [x] 3.3 N/A — kept docling as fallback (not the "no code change" branch),
      see 3.2.

## 4. Semantic re-analysis and docling removal (2026-07-09)

- [x] 4.1 Extend corpus with 4 files targeting axes the original 4-category
      set never covered (CJK, math, infographics) — see 2.3 above and
      `bench/corpus/README.md`.
- [x] 4.2 Re-score all outputs for LLM-semantic-recoverability (not
      visual/structural fidelity) — finding: pymupdf4llm's structural defects
      are cosmetic (data intact, attributable, reconstructable); markitdown
      has two genuine semantic failures (table_heavy reading-order fusion,
      math_heavy's severed π-bounds claim); docling has one total,
      unrecoverable failure (100% formula loss). See design.md D5.
- [x] 4.3 Decision: **drop docling entirely** — `.pdf` chain becomes
      `[PymupdfLlmEngine]`, no fallback. Primary reason: semantic evidence
      (4.2). Secondary reason: removes the `typer<0.25` conflict from
      `convert-md[documents]` for every consumer, not just a2web-shaped ones
      (D1/D3, already established). Recorded in design.md D5 and ledger entry
      `ledger/0035-convert-md-drop-docling.toml` (supersedes 0034).
- [x] 4.4 Applied: `DoclingEngine` removed from `engines.py`/`dispatch.py`/
      `__init__.py`; `docling` dropped from `documents` extra and keywords;
      `convert-md-v0.5.0` (behavior-changing engine removal — minor bump per
      the shelf's semver discipline). `bench/` keeps `run_docling.py` as an
      isolated probe (D4: re-verifiable later even though not a runtime dep).
      `make check` green.
