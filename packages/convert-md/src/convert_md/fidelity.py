"""Fidelity heuristic (ADR 0021 / R142) — grade a conversion without a model.

A composite of five cheap signals over the produced Markdown:

1. **Yield** — output length relative to the source byte size. A near-empty
   result from a non-trivial source means the engine dropped almost everything.
2. **Structure** — whether tables/headings/code survived anywhere in the
   document (their absence in a long document is suspicious but not damning
   on its own).
3. **Encoding garbage** — density of replacement chars / control bytes, which
   flags an encoding or OCR failure.
4. **Glyph-ID leakage** — density of raw ``(cid:N)`` tokens, a specific,
   well-known tell for a PDF font's ToUnicode mapping failing to resolve
   (thresholds calibrated 2026-07-09 against real markitdown/CJK bench output
   — see ``bench/results/2026-07-09-findings.md``, `garbage_density` alone
   never catches this: cid tokens are plain printable ASCII, not garbage
   bytes, and get diluted below the char-density threshold by their own
   length).
5. **Shattered-table shape** — density of isolated, short, numeric-only
   lines, the shape a table takes when an engine drops pipe/row syntax
   entirely and emits one cell per line with no row/column markup (calibrated
   against the same corpus: real markdown tables never trip this, even
   numeric-dense ones, because their cells sit inside ``| … |`` lines).

The grade is conservative: clean text with reasonable yield is ``high``; thin
or garbled output is ``partial``; essentially-empty output is ``failed``. The
real OCR-confidence path is reserved for opt-in VLM engines.

**Known, accepted limitation** (not fixed by the 2026-07-09 signals above):
this heuristic cannot detect *semantic* corruption where the text stays
clean, well-formed, and structurally intact but is reordered, fused, or
silently dropped in a way that changes meaning (e.g. two unrelated sentences
concatenated across a column break, or a numeric claim severed from its own
value elsewhere in the file — both confirmed real defects in
``bench/results/2026-07-09-findings.md``'s "Extended corpus addendum"). Only
a model-based judge can catch that class of defect; this module stays
model-free by design (see module name), so it stays blind to it on purpose.
Flag conversions where that risk matters for opt-in LLM-graded review, not
this heuristic.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from convert_md.base import Fidelity

_GARBAGE_RE = re.compile(r"[�\x00-\x08\x0b\x0c\x0e-\x1f]")
_CID_TOKEN_RE = re.compile(r"\(cid:\d+\)")
_NUMERIC_LINE_RE = re.compile(r"^\s*[\d,.\-()%$¥€]{1,20}\s*$")
_TABLE_RE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
_HEADING_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)

# Calibrated 2026-07-09 against packages/convert-md/bench/outputs/ (39 real
# conversions, 5 engines x 8 documents) — not guessed. Known-bad cases sat at
# 0.075-0.126; every known-clean case sat at 0.0. 0.03 leaves comfortable
# margin on both sides.
_CID_LINE_FRACTION_THRESHOLD = 0.03
# Known-bad (unstructured's shattered financial table): 0.562. Highest
# known-clean/legitimately-numeric-dense case (pymupdf4llm's jammed-but-
# intact table rows): 0.260. 0.35 sits in the gap.
_NUMERIC_LINE_FRACTION_THRESHOLD = 0.35
_MIN_LINES_FOR_SHATTER_CHECK = 20  # avoid false positives on tiny documents


if TYPE_CHECKING:
    _Verdict = tuple[Fidelity, list[str], list[str]]


def _check_garbage(markdown: str) -> _Verdict | None:
    garbage = len(_GARBAGE_RE.findall(markdown))
    garbage_density = garbage / max(len(markdown), 1)
    if garbage_density > 0.02:
        return "partial", ["encoding"], [f"encoding_garbage_density={garbage_density:.3f}"]
    return None


def _check_cid_leak(lines: list[str]) -> _Verdict | None:
    cid_lines = sum(1 for ln in lines if _CID_TOKEN_RE.search(ln))
    cid_line_fraction = cid_lines / max(len(lines), 1)
    if cid_line_fraction > _CID_LINE_FRACTION_THRESHOLD:
        return "partial", ["encoding"], [f"cid_glyph_leak_line_fraction={cid_line_fraction:.3f}"]
    return None


def _check_shattered_table(lines: list[str]) -> _Verdict | None:
    if len(lines) < _MIN_LINES_FOR_SHATTER_CHECK:
        return None
    numeric_lines = sum(1 for ln in lines if _NUMERIC_LINE_RE.match(ln))
    numeric_line_fraction = numeric_lines / len(lines)
    if numeric_line_fraction > _NUMERIC_LINE_FRACTION_THRESHOLD:
        return "partial", ["table_structure"], [f"shattered_table_numeric_line_fraction={numeric_line_fraction:.3f}"]
    return None


def _check_yield(markdown: str, source_size: int) -> _Verdict | None:
    # Very little text out of a sizeable source → likely lossy.
    if source_size > 4096 and len(markdown) < source_size * 0.02:
        return "partial", ["content"], [f"low_yield={len(markdown)}/{source_size}"]
    return None


def _check_structure(markdown: str, source_size: int) -> _Verdict | None:
    has_table = bool(_TABLE_RE.search(markdown))
    has_heading = bool(_HEADING_RE.search(markdown))
    if source_size > 32768 and not has_table and not has_heading:
        # A large document with no structure at all often means flattening.
        return "partial", ["structure"], ["no_tables_or_headings_in_large_doc"]
    return None


def grade(*, markdown: str, source_size: int, check_yield: bool = True) -> tuple[Fidelity, list[str], list[str]]:
    """Return ``(fidelity, lost, warnings)`` for a conversion output.

    ``check_yield`` should be False for ZIP-container formats (docx/xlsx/pptx)
    and PDFs, whose on-disk byte size is not comparable to extracted text length
    — only text-like sources (html) get the output/input ratio check.
    """
    stripped = markdown.strip()
    if not stripped:
        return "failed", ["all"], ["empty_output"]

    lines = [ln for ln in markdown.splitlines() if ln.strip()]
    verdict = (
        _check_garbage(markdown)
        or _check_cid_leak(lines)
        or _check_shattered_table(lines)
        or (_check_yield(markdown, source_size) if check_yield else None)
        or _check_structure(markdown, source_size)
    )
    if verdict is not None:
        return verdict
    return "high", [], []


__all__ = ["grade"]
