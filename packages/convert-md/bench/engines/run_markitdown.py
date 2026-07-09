"""Probe runner: markitdown.

Already a real `convert-md[documents]` dependency — run directly against the
package's own env, no isolation needed (D4).
"""

import sys
import time
from pathlib import Path


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    from markitdown import MarkItDown

    t0 = time.monotonic()
    md_converter = MarkItDown()
    result = md_converter.convert(src)
    md = result.text_content
    elapsed = time.monotonic() - t0

    Path(dst).write_text(md)
    print(f"elapsed_s={elapsed:.2f} chars={len(md)}", file=sys.stderr)


if __name__ == "__main__":
    main()
