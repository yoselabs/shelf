"""Probe runner: markitdown.

Already a real `convert-md[documents]` dependency — run directly against the
package's own env, no isolation needed (D4).
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
