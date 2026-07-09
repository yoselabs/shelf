# Bench corpus

Public-domain (or, where noted, openly-licensed-for-non-redistribution) PDFs
only — never a user's own document, per design.md D2. Each trimmed to a small
page range so the full engine matrix runs in reasonable time; the *class* of
document matters for the fidelity axes, not full-book coverage.

| File | Source | License | Pages kept | Why this document |
|---|---|---|---|---|
| `prose_report.pdf` | [arXiv:2303.08774](https://arxiv.org/abs/2303.08774) ("GPT-4 Technical Report") | arXiv non-exclusive license (author copyright) | 2-11 of 100 | Baseline prose + headings, minimal tables/figures |
| `table_heavy.pdf` | [IRS Form 1040 Instructions](https://www.irs.gov/pub/irs-pdf/i1040gi.pdf) | US government work — public domain | 101-112 of 126 | Genuinely public-domain, dense tax-bracket / worksheet tables |
| `multicolumn_academic.pdf` | [arXiv:1512.03385](https://arxiv.org/abs/1512.03385) ("Deep Residual Learning for Image Recognition") | arXiv non-exclusive license (author copyright) | 1-8 of 12 | Two-column CVPR layout, figures + result tables, reading-order test |
| `scanned_ocr.pdf` | [Internet Archive: leavesofgrass00whit](https://archive.org/details/leavesofgrass00whit) (Whitman, *Leaves of Grass*, early edition scan) | Public domain (pre-1929 US publication) | 11-18 of ~300 | Genuine scanned page images, no embedded text layer — OCR fidelity test |
| `math_heavy.pdf` | [arXiv:2502.17533](https://arxiv.org/abs/2502.17533) ("From Euler to AI: Unifying Formulas for Mathematical Constants") | arXiv non-exclusive license (author copyright) | 1, 3-10, 12 of 82 (page 2 skipped — an 8MB embedded figure that bloated the trim for no fidelity value) | Dense LaTeX-rendered formula blocks, inline math, theorem/proof structure — a fidelity axis the original 4-category corpus didn't cover |
| `ja_service_manual.pdf` | [Brother Innovis 80 sewing machine manual](https://download.brother.com/welcome/doch010033/inov80ug01jp.pdf) (official manufacturer download) | Copyrighted, freely published by Brother for product owners/support use (not public domain) | 25-34 of 168 | Japanese-language (CJK) instructional content — numbered steps, UI screenshots, mixed vertical/horizontal label callouts. Non-Latin script + real service-manual shape (the original "doc link problem" a2web trigger case) that no file in the base corpus tested |
| `zh_service_manual.pdf` | [Brother DCP-9020CDN manual, Simplified Chinese](https://download.brother.com/welcome/doc003072/dcp9020cdn_sch_busr_lef348020_a.pdf) (official manufacturer download) | Copyrighted, freely published by Brother for product owners/support use (not public domain) | 15-24 of 180 | Simplified-Chinese (CJK) instructional content — control-panel diagrams, numbered callouts. Second CJK script family, distinct from Japanese's mixed kanji/kana/furigana shape |
| `investor_infographics.pdf` | [Toyota Motor Corporation Integrated Report 2025](https://global.toyota/pages/global_toyota/ir/library/annual/2025_001_integrated_en.pdf) (official IR library) | Copyrighted, freely published by Toyota for public/investor consumption (not public domain) | 162-166 of 168 (re-trimmed 2026-07-09 — the original 12-23 landed on CEO-message prose, not chart content; "History" timeline infographic + "Domestic/Overseas Vehicle Production" chart + "Financial Summary (Consolidated)" multi-year data table) | Infographic-dense investor-report layout — timeline graphics, production charts, and a real financial data table. Tests text/table content retention when the source layout is chart/graphic-driven, not prose |

## Deviation from strict "public domain only"

Six of ten files are not strictly public domain:

- `prose_report.pdf`, `multicolumn_academic.pdf`, `math_heavy.pdf` are arXiv
  papers (authors retain copyright; arXiv holds a non-exclusive distribution
  license). Substituting genuinely public-domain equivalents proved harder to
  source reliably than expected — public-domain-and-conveniently-hosted
  rarely overlap for *modern-shaped* layouts (multi-column CVPR/IEEE
  templates, LaTeX-rendered math) specifically.
- `ja_service_manual.pdf`, `zh_service_manual.pdf`, `investor_infographics.pdf`
  are manufacturer/corporate documents: copyrighted, but officially and
  freely published by their owners (Brother, Toyota) for exactly the kind of
  use this bench makes of them (reading, not redistribution-for-profit).
  Genuinely public-domain CJK-script service manuals or infographic-dense
  investor reports do not meaningfully exist — the document *class* itself
  is inherently commercial.

design.md's actual stated concern behind "public domain only" was **"never
the user's own documents"** — a privacy/scope boundary, not copyright
purism. All six files satisfy that intent (freely and legally readable by
anyone, not private data) even though they fail strict public-domain status.
Flagging this explicitly rather than silently reinterpreting the rule;
revisit if this corpus is ever redistributed rather than used as a private,
local bench fixture.
