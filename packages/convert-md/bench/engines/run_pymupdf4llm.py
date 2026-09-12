"""Probe runner: pymupdf4llm.

NOT a convert-md dependency — invoked only via `uv run --with pymupdf4llm`
(isolated, transient install per D4).
"""

import sys
import time
from pathlib import Path


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
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
