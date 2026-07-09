# convert-md

Opinionated document → Markdown conversion. Each format has a primary engine and a fallback chain;
the dispatcher walks the chain and only declares `failed` when every engine gives up. Legacy binary
Office formats are normalized through LibreOffice headless, then re-dispatched. Every conversion is
graded for fidelity by a cheap, model-free heuristic (yield / structure / garbage).

```python
from convert_md import convert

result = convert(Path("report.pdf"))
result.body_markdown   # the converted text
result.fidelity        # "high" | "partial" | "failed"
result.engine          # "<engine>@<version>"
```

Engines wrapped: pymupdf4llm, no fallback (pdf, revised v0.5.0 — docling dropped entirely, see
`bench/results/2026-07-09-findings.md` and design.md D5), pandoc (docx), markitdown (pptx/xlsx), trafilatura +
html2text (html), openpyxl (xlsx fallback). Engine choice is a code-level default (R142), not a
config file.

PDF support ships as two extras with the same engine either way: `convert-md[pdf]` (just
pymupdf4llm — no ML/GPU deps, conflict-free for any consumer) and `convert-md[documents]` (the
full office+PDF set). A re-runnable fidelity comparison harness lives in `bench/` — see
`bench/results/` for the dated findings behind pymupdf4llm-only, including why docling (once the
fidelity ceiling, tried as a fallback) was dropped rather than kept.

Extracted from a2kay as its first reusable micro-software; the conversion *mechanism* lives here,
the consumer keeps its own presentation policy. No dependency on a2kay.
