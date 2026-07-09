"""Probe runner: unstructured.

NOT a convert-md dependency — invoked only via `uv run --with
"unstructured[pdf]"` (isolated, transient install per D4). Uses
strategy="fast" (pdfminer-based, no OCR) since this sandbox has no
`tesseract` installed — the "hi_res"/"ocr_only" strategies would silently
degrade or fail without it. That itself is a fidelity data point: unstructured's
best PDF quality requires system binaries beyond what a pure `uv add` gets you.
"""

import sys
import time
from pathlib import Path

_CATEGORY_PREFIX = {
    "Title": "## ",
    "Header": "## ",
}


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    from unstructured.partition.pdf import partition_pdf

    t0 = time.monotonic()
    elements = partition_pdf(filename=src, strategy="fast")
    lines = []
    for el in elements:
        category = type(el).__name__
        prefix = _CATEGORY_PREFIX.get(category, "")
        lines.append(f"{prefix}{el.text}")
    md = "\n\n".join(lines)
    elapsed = time.monotonic() - t0

    Path(dst).write_text(md)
    print(f"elapsed_s={elapsed:.2f} chars={len(md)}", file=sys.stderr)


if __name__ == "__main__":
    main()
