## Context

The `pdf-engine-verification` change (archived) established the shelf's method
for making an inherited engine choice evidence-backed: a small re-runnable
bench under `packages/convert-md/bench/`, a public corpus, transient isolated
per-engine installs (`uv run --with <engine>`), a human-judged fidelity rubric,
and a dated findings doc. It overturned the inherited PDF choice on evidence
(docling dropped entirely, `.pdf` → pymupdf4llm-only).

This change applies the same method to the **docx** path, which was never
benched — inherited from R142 on one claim (pandoc `--track-changes=all`
preserves redlines). The bench apparatus is PDF-only today: `run_bench.py`
globs `corpus/*.pdf` and iterates a hardcoded 5-PDF-engine list; there are no
docx fixtures, runners, or scores.

Two decisions carry beyond convert-md and get extracted as shelf primitives:
the generic-first/specific-second reasoning discipline (D5) and `WORKFLOW:
BENCH` (D6).

## Decisions

### D1 — The docx question is narrower than PDF, and collapses toward one axis

PDF is a lossy layout format: every engine reverse-engineers structure from
positions, so they diverge everywhere (the PDF bench found dramatic spread —
heading nesting, reading order, table structure all disagreed across engines).
docx is **semantic OOXML**: the heading *is* `<w:pStyle w:val="Heading1">`, the
table *is* `<w:tbl>`. There is almost nothing to reverse-engineer, so engines
should converge on the common grid and diverge only at capability edges:

- **tracked changes / comments** — pandoc's sole differentiator
- **OMML equations** (Word's native math) — engine handling varies
- **embedded-image handling** — extract / reference / drop
- (footnotes, endnotes, nested lists, nested tables — likely convergent, still
  scored as regression anchors)

Consequence: the docx bench is a **capability grid**, not a document-fidelity
sweep. Fewer, sharper fixtures — one capability each — beat a handful of
realistic-but-confounded documents. The interesting question is not "which
engine reads docx better" (they read the easy 90% fine) but "does anyone feed
the hard 10%, and does the engine choice matter there."

### D2 — Isolate by *synthesis* for docx (the inverse of the PDF corpus rule)

The PDF corpus deliberately used real, downloaded documents (arXiv, IRS, Brother
manuals) because PDF fidelity is about messy real-world layout you cannot
synthesize — a hand-made single-feature PDF is *easier than reality* and would
mask the exact divergence the bench exists to expose.

docx inverts this. Because it is semantic, a **synthesized** fixture carrying
exactly one feature (one tracked insertion and nothing else; one OMML equation
and nothing else) gives perfectly clean failure attribution with **no realism
lost** — there is no lossy layout to lose. So:

- **Committed fixtures are synthesized**, one capability per file, authored via
  `python-docx` (or scripted Word-equivalent output) and checked in under
  `bench/corpus/docx/`. Each documented in `bench/corpus/README.md` with its
  isolated capability, exactly as the PDF files are documented by axis.
- **Exception:** OMML math and embedded-image handling have real-Word quirks
  synthesis reproduces poorly. For those, prefer one or two genuinely public
  documents (or a real file authored *for* the bench and released public), same
  license discipline as the PDF corpus.
- **The user's own docx are never committed.** design.md D2 of the PDF change
  states the real rule behind "public domain only": *never the user's own
  documents* (privacy/scope, not copyright purism). The user's real files are
  used locally to (a) discover which capabilities actually occur in practice
  and (b) sanity-check the grades — inputs to judgment, not corpus artifacts.

**The isolation principle transfers to any future bench; the technique does
not.** Semantic formats (docx/pptx/xlsx) → isolate by synthesis. Lossy formats
(PDF, scans) → isolate by *selection* of real documents. This asymmetry is
recorded in `WORKFLOW: BENCH` (D6).

### D3 — Candidate set: three engines, one of them scored in two modes

| Engine | Weight | Tracked changes | Notes |
|---|---|---|---|
| pandoc (`pypandoc-binary`) | ~100MB+ bundled binary | only engine that *can* render redlines (`--track-changes=all`) | current primary; heavy |
| markitdown | already a `documents`-extra dep | no | routes docx→HTML via `mammoth~=1.11.0` internally |
| mammoth → HTML chain | featherweight (mammoth's only dep is `cobble`) | no | docx→HTML→ convert-md's existing trafilatura/html2text base path |

- **pandoc is scored in both modes:** `--track-changes=accept` (its default,
  clean final text) *and* `--track-changes=all` (redline markup). This
  quantifies exactly what the flagship flag does, rather than assuming it.
- **markitdown vs raw-mammoth** are near-identical engines (markitdown wraps
  mammoth); scoring both reveals whether markitdown's wrapper adds or loses
  anything vs mammoth feeding convert-md's own HTML chain. If identical, prefer
  whichever unifies best (markitdown already handles pptx/xlsx) or is lightest
  (raw mammoth reuses base deps).
- Fetching `pypandoc-binary` for the bench is fine and expected (user
  approved) — the bench is exactly where we pay to compare before deciding.

### D4 — Harness reuse, not a parallel harness

The docx grid runs *inside* the existing `bench/` — same isolated-install
pattern (`uv run --with <engine>`), same `bench/engines/run_<engine>.py` runner
shape, same `bench/outputs/<engine>__<fixture>.md` layout, same model-free
fidelity grade, same dated `bench/results/` findings doc. Concretely:

- `run_bench.py` gains a format dimension (glob `corpus/**/*.docx` alongside
  `corpus/*.pdf`; select the engine list by format) rather than a second
  orchestrator.
- New runners: `run_pandoc.py` (both modes), `run_mammoth.py`; markitdown's
  existing runner is reused if format-agnostic, else a thin docx entry added.
- `deptry`'s `extend_exclude = ["bench"]` already covers the new bench-only
  engine imports (mammoth, pypandoc) — no dependency-hygiene change needed.

### D5 — Extract `generic-first, specific-second` as a resolution now

Ready to write immediately (this change is its worked example):

> An agent shaping a shelf package reasons about the capability **generically
> first** — what does "convert docx to markdown" need across the class of
> inputs at large — and uses the live consumer **second, only to weight** which
> capabilities are common (belong in the light default) versus rare (acceptable
> behind an opt-in extra or graceful degradation). The consumer defines the
> *weighting*, never the *capability set*. Corollary: never scope a package's
> capability grid down to a single consumer's current diet — that is how a
> package accretes hidden assumptions and stops being reusable substrate.

This is a governance resolution (next number in `docs/resolutions/`), distilled
into `agent-loop.md` in the same commit (enforced by
`tests/test_resolution_distillation.py`). It generalizes the correction made
mid-exploration: the initial framing over-anchored on "what does a2kay feed,"
when the shelf's own doctrine makes convert-md generic-first, consumer-second.

### D6 — Extract `WORKFLOW: BENCH`, finalized *from* this run

The shelf now has two instances of one exercise (PDF bench, docx bench). Two is
enough to see the pattern; writing it *before* the second instance would be
inventing, not extracting (the shelf's own rule, and how resolution 0009 was
written — after walking PROMOTE end-to-end). So: draft the skeleton at the
start of the bench, finalize the workflow text once the docx run confirms each
step generalizes. Expected shape of the named workflow:

1. **Frame the question** as build-vs-adopt / keep-vs-replace on a *specific
   capability*, not "which tool is best" abstractly.
2. **Corpus by isolation** — one capability per fixture. Synthesize for
   semantic formats, select real documents for lossy ones (D2). Never the
   user's own data; document each fixture's isolated axis.
3. **Transient isolated installs** — each engine via `uv run --with <engine>`;
   never a declared dependency of the package just to bench it.
4. **Model-free fidelity grade** — human-judged rubric on named axes, evidence
   quoted from outputs; not LLM-judged.
5. **Dated findings doc** under `bench/results/`, committed as an artifact.
6. **Decide → ledger row** — evidence-backed keep/replace/tier, recorded; the
   bench answers "which engine," a separate call answers "is it worth it."

Open until the run: whether BENCH is a full peer of PROMOTE/RECEIVE/RECONCILE
or a sub-procedure referenced by them. Decide in tasks after the run.

### D7 — HTML is two intents (extract vs render), keyed by `source_kind` (decided 2026-07-10)

Surfaced mid-run while deciding how mammoth's HTML reaches markdown. The naïve
move — route docx through the existing `convert_html()` — was tested and failed
badly: trafilatura (its primary) is a web-page boilerplate *remover*, and on a
clean docx-derived fragment it stripped all headings/emphasis and exploded the
table, while grading `high`. A separate test confirmed trafilatura handles a
*real full page* correctly (keeps headings/marked-header table, strips
nav/footer), so the web path is healthy — the two must simply never cross.

The root cause is a conceptual leak: "trafilatura is the HTML→markdown
converter" is wrong. It is the best web-page *extractor*. HTML carries two
intents, and the MIME type under-determines which you want:

- **extract** (`source_kind="web_page"`, default) — boilerplate-bearing page,
  recover main content, drop chrome → trafilatura → html2text.
- **render** (`source_kind="clean"`) — already-clean HTML (mammoth's docx
  output), lose nothing → html2text only, bypassing the web extractor.

**Decision:** add `source_kind: Literal["web_page", "clean"]` to `convert_html`
(default `web_page`, so a2web is untouched). The docx path (`MammothEngine`)
calls `convert_html(html, source_kind="clean")` — so docx and the web fallback
share **one** render back-end (html2text), rather than introducing a third
opinion (markitdown's markdownify). The kind is knowable statically at each call
site; the explicit param was chosen over two separate functions (the user's
call) for a single documented entry point.

**Deferred (protection is earned):** an `.html`-*file* selector. `convert(path)`
routes `.html` → trafilatura (assumes web page); a clean `.html` file can't be
disambiguated by extension. No consumer feeds clean `.html` files today, so the
selector is not built — documented as the place it would go. The broader "unify
convert-md on one canonical render back-end (and bench html2text vs markdownify
vs … as *the* renderer)" is a separate follow-up; it touches a2web's live path
and deserves its own real-web-corpus BENCH run.

## Non-Goals

- Re-litigating pptx/xlsx (already uncontested markitdown-primary) unless the
  mammoth/markitdown comparison surfaces a reason to.
- Round-tripping a2kay's real corpus through the new path — a2kay's follow-up.
- LLM-judged scoring — model-free grade only, consistent with the PDF bench.
- Building tiered-install plumbing before the evidence says a tier is warranted.

## Open Questions

- Does a2kay's real docx diet contain *any* tracked-changes or commented files?
  (Weighting input per D5; discovered locally, not committed.)
- If markitdown and raw-mammoth score identically, does convert-md prefer the
  unification (markitdown for all Office) or the lighter reuse (mammoth → own
  HTML chain)? Decide from the weight/coupling tradeoff after scoring.
- Is `WORKFLOW: BENCH` a peer workflow or a sub-procedure (D6)?
