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
`bench/results/2026-07-09-findings.md` and design.md D5), mammoth (docx, revised v0.7.0 — pandoc
dropped, see `bench/results/2026-07-10-docx-findings.md`), markitdown (pptx/xlsx + docx fallback),
trafilatura + html2text (html), openpyxl (xlsx fallback). Engine choice is a code-level default
(R142), not a config file.

HTML is handled by *source kind*, not MIME type: `convert_html(html, source_kind="web_page")`
(default) extracts main content from a boilerplate-bearing page (trafilatura); `source_kind="clean"`
faithfully renders already-clean HTML (html2text), and is what the docx path uses after mammoth. See
`convert_md/html.py` for why crossing them damages the output.

PDF support ships as two extras with the same engine either way: `convert-md[pdf]` (just
pymupdf4llm — no ML/GPU deps, conflict-free for any consumer) and `convert-md[documents]` (the
full office+PDF set). A re-runnable fidelity comparison harness lives in `bench/` — see
`bench/results/` for the dated findings behind pymupdf4llm-only, including why docling (once the
fidelity ceiling, tried as a fallback) was dropped rather than kept.

## Check your engines are installed: `missing_engines`

`convert` never raises, so a missing engine library does not crash anything. It turns
every file of that format into `fidelity="failed"`, quietly. That is how a bare
`convert-md` pin behaved when v0.3.0 moved the document engines behind
`[documents]`: installs fine, imports fine, converts nothing. Put the formats you
promise in a test:

```python
from convert_md import missing_engines

def test_document_engines_are_installed():
    assert missing_engines([".pdf", ".docx", ".pptx", ".xlsx"]) == {}
    # else e.g. {".docx": ["MammothEngine: module 'mammoth' not installed"]}
```

It reports a format with no engine chain, an engine whose library is missing, and a
legacy format (`.doc`/`.ppt`) with no LibreOffice on `PATH`. Nothing is imported to
check. It runs against whatever version you have pinned, so it fails at the moment
you bump the pin, which is when the fix is cheap.

Extracted from a2kay as its first reusable micro-software; the conversion *mechanism* lives here,
the consumer keeps its own presentation policy. No dependency on a2kay.
