"""Probe runner: docling.

Dropped from `convert-md[documents]` entirely in v0.5.0 (design.md D5) — no
longer a real dependency. Invoked only via `uv run --with docling` (isolated,
transient install per D4), kept so future re-verification stays possible.
"""

import sys
import time
from pathlib import Path


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    # Force CPU: docling's MPS (Apple Silicon GPU) path errors on float64 ops
    # in this docling/torch version combo — a real, reproducible platform bug,
    # not a fidelity question. Recorded as a note, worked around so the
    # comparison isn't blocked by it.
    pipeline_options = PdfPipelineOptions()
    pipeline_options.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CPU)

    t0 = time.monotonic()
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)})
    result = converter.convert(src)
    md = result.document.export_to_markdown()
    elapsed = time.monotonic() - t0

    Path(dst).write_text(md)
    print(f"elapsed_s={elapsed:.2f} chars={len(md)}", file=sys.stderr)


if __name__ == "__main__":
    main()
