"""Fidelity heuristic (ADR 0021 / R142) — grade a conversion without a model.

A composite of three cheap signals over the produced Markdown:

1. **Yield** — output length relative to the source byte size. A near-empty
   result from a non-trivial source means the engine dropped almost everything.
2. **Structure** — whether tables/headings/code survived (their absence in a
   long document is suspicious but not damning on its own).
3. **Garbage** — density of replacement chars / control bytes, which flags an
   encoding or OCR failure.

The grade is conservative: clean text with reasonable yield is ``high``; thin
or garbled output is ``partial``; essentially-empty output is ``failed``. The
real OCR-confidence path is reserved for opt-in VLM engines.
"""

from __future__ import annotations

import re

from convert_md.base import Fidelity

_GARBAGE_RE = re.compile(r"[�\x00-\x08\x0b\x0c\x0e-\x1f]")
_TABLE_RE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
_HEADING_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)


def grade(*, markdown: str, source_size: int, check_yield: bool = True) -> tuple[Fidelity, list[str], list[str]]:
    """Return ``(fidelity, lost, warnings)`` for a conversion output.

    ``check_yield`` should be False for ZIP-container formats (docx/xlsx/pptx)
    and PDFs, whose on-disk byte size is not comparable to extracted text length
    — only text-like sources (html) get the output/input ratio check.
    """
    lost: list[str] = []
    warnings: list[str] = []

    stripped = markdown.strip()
    if not stripped:
        return "failed", ["all"], ["empty_output"]

    garbage = len(_GARBAGE_RE.findall(markdown))
    garbage_density = garbage / max(len(markdown), 1)
    if garbage_density > 0.02:
        warnings.append(f"encoding_garbage_density={garbage_density:.3f}")
        return "partial", ["encoding"], warnings

    # Yield: very little text out of a sizeable source → likely lossy.
    if check_yield and source_size > 4096 and len(markdown) < source_size * 0.02:
        warnings.append(f"low_yield={len(markdown)}/{source_size}")
        return "partial", ["content"], warnings

    has_table = bool(_TABLE_RE.search(markdown))
    has_heading = bool(_HEADING_RE.search(markdown))
    if source_size > 32768 and not has_table and not has_heading:
        # A large document with no structure at all often means flattening.
        lost.append("structure")
        warnings.append("no_tables_or_headings_in_large_doc")
        return "partial", lost, warnings

    return "high", lost, warnings


__all__ = ["grade"]
