"""Probe runner: marker.

NOT a convert-md dependency — invoked only via `uv run --with marker-pdf`
(isolated, transient install per D4). GPU-preferred; runs CPU-only here since
this sandbox has no GPU. Expected to be slow (design.md D2: "5-10x slower
without GPU") — that expectation is itself part of what this probe is
verifying, not just the fidelity axes.
"""

import argparse
import sys
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("src", help="the file to convert")
    parser.add_argument("dst", help="where to write the markdown")
    args = parser.parse_args()
    src, dst = args.src, args.dst
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered

    t0 = time.monotonic()
    converter = PdfConverter(artifact_dict=create_model_dict())
    rendered = converter(src)
    md, _, _ = text_from_rendered(rendered)
    elapsed = time.monotonic() - t0

    Path(dst).write_text(md)
    print(f"elapsed_s={elapsed:.2f} chars={len(md)}", file=sys.stderr)


if __name__ == "__main__":
    main()
