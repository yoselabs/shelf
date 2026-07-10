## 1. Discover the capability grid (judgment inputs, nothing committed)

- [x] 1.1 Enumerate the docx capabilities worth scoring (D1): tracked changes,
      OMML equations, embedded images, footnotes/endnotes, nested tables,
      nested lists, headings/styles, clean-prose baseline. Confirm the set
      against a scan of the user's real docx locally (which capabilities
      actually occur) — record the *weighting* observation in the findings
      doc later; **commit no user files** (D2).

## 2. Corpus — synthesized per-capability fixtures

- [x] 2.1 Author one synthesized `.docx` per capability via `python-docx`
      (tracked-changes, footnote, nested-table, nested-list, headings/styles,
      clean-baseline), one feature each (D2). Land under
      `bench/corpus/docx/`.
- [x] 2.2 For OMML math and embedded-image (synthesis-weak, D2 exception),
      source one or two genuinely public real docx, or author-and-release a
      file for the bench; same license discipline as the PDF corpus.
- [x] 2.3 Document every fixture in `bench/corpus/README.md` with its isolated
      capability + source, matching the existing per-axis PDF table.

## 3. Harness — extend, don't fork (D4)

- [x] 3.1 Add a format dimension to `run_bench.py`: glob `corpus/**/*.docx`
      alongside `corpus/*.pdf`; select the engine list per format.
- [x] 3.2 Add runners: `bench/engines/run_pandoc.py` (score BOTH
      `--track-changes=accept` and `--track-changes=all`, D3),
      `run_mammoth.py` (mammoth → HTML → convert-md's HTML chain). Reuse the
      markitdown runner if format-agnostic, else add a thin docx entry.
- [x] 3.3 Run the full docx grid; capture outputs to
      `bench/outputs/<engine>__<fixture>.md`. Confirm `deptry`'s
      `extend_exclude=["bench"]` still covers the new bench-only imports.

## 4. Score and write findings

- [x] 4.1 Human-judge each output on the D1 capability axes — model-free
      rubric, evidence quoted from the outputs (same discipline as the PDF
      findings). Key questions: does pandoc-accept differ from
      markitdown/mammoth on the common grid at all? What exactly does
      pandoc-all inject (redline markup) and is it ever wanted? Do
      markitdown and raw-mammoth diverge?
- [x] 4.2 Write `bench/results/<date>-docx-findings.md` — the dated evidence
      doc, committed as an artifact. Include the a2kay-diet weighting note.

## 5. Decide and apply (convert-md)

- [x] 5.1 Decision from evidence: single engine (likely markitdown/mammoth) or
      the tiered shape (light default + opt-in pandoc extra + graceful
      degradation with `lost=["tracked_changes"]`). Record in a new design
      decision + a `ledger/00NN-*.toml` `delivery` row.
- [x] 5.2 Apply to `convert-md`: update `dispatch.py`'s `.docx` chain and the
      `documents`/new extras in `pyproject.toml`; if pandoc is dropped from the
      mandatory extra, remove `pypandoc-binary` there. Update `engines.py`
      (drop/relocate `PandocEngine` per the decision) and the README.
- [x] 5.3 Re-cut a `convert-md` version (behavior-changing → minor bump per the
      shelf's semver discipline). `make check` green — whole-repo, no
      carve-outs. Keep any dropped engine's `run_*.py` as an isolated bench
      probe (D4: re-verifiable later even if not a runtime dep).

## 6. Extract shelf primitive: generic-first, specific-second (D5)

- [ ] 6.1 Write `docs/resolutions/00NN-generic-first-specific-second.md`
      (Status/Expires/Track/Distilled-into), stating the rule + the corollary
      (never scope a package's capability grid to one consumer's diet).
- [ ] 6.2 Distill it into `agent-loop.md` (the package-reasoning discipline) in
      the **same commit** — `tests/test_resolution_distillation.py` enforces
      the coupling. This change is the resolution's cited worked example.

## 7. Extract shelf primitive: WORKFLOW: BENCH (D6)

- [ ] 7.1 Draft the `WORKFLOW: BENCH` skeleton in `agent-loop.md` at the start
      of the bench (the 6-step shape in design.md D6).
- [ ] 7.2 Finalize it *from* the completed docx run — reconcile every step
      against what actually happened across BOTH the PDF and docx benches
      (extracted, not invented). Decide the open question: peer workflow vs
      sub-procedure. Add its `OUTPUT` + close-the-loop step (resolution 0009).
- [ ] 7.3 If it warrants a resolution of its own (a new named workflow is a
      governance fact), write it and distil in the same commit; else fold the
      citation into the existing workflow set.

## 8. Close the loop (resolution 0009)

- [ ] 8.1 `make catalog` if `catalog/*.toml` / `use-cases/*.toml` changed;
      ledger rows written (delivery for the convert-md re-cut; verdict only if
      a consumer repoint actually lands in this change — it won't, that's
      a2kay's follow-up).
- [ ] 8.2 Prune the `docs/backlog.md` "Verify — convert-md's docx engine
      choice" line (this change *is* that verification).
- [ ] 8.3 `make check` green; work merged to `main` and pushed; no dangling
      worktree/branch. `openspec archive docx-engine-verification`.
