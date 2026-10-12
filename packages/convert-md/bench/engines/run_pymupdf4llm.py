"""Probe runner: pymupdf4llm.

NOT a convert-md dependency — invoked only via `uv run --with pymupdf4llm`
(isolated, transient install per D4).
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
    import pymupdf4llm

    t0 = time.monotonic()
    md = pymupdf4llm.to_markdown(src)
    if not isinstance(md, str):  # to_markdown returns page chunks only when asked for them
        msg = f"pymupdf4llm returned {type(md).__name__}, expected str"
        raise TypeError(msg)
    elapsed = time.monotonic() - t0

    Path(dst).write_text(md)
    print(f"elapsed_s={elapsed:.2f} chars={len(md)}", file=sys.stderr)


if __name__ == "__main__":
    main()
