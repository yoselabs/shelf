"""Probe runner: pandoc (via pypandoc-binary), docx -> gfm markdown.

Scored in BOTH track-changes modes (design.md D3) so the bench quantifies
pandoc's sole differentiator instead of assuming it:

    argv[3] = "accept" (default) -> --track-changes=accept  (clean final text)
    argv[3] = "all"              -> --track-changes=all      (renders redlines)

Isolated install (D4): pypandoc-binary is fetched only for the bench, matching
convert-md's real docx invocation (`gfm`, `--wrap=none`).
"""

import argparse
import sys
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("src", help="the file to convert")
    parser.add_argument("dst", help="where to write the markdown")
    parser.add_argument("mode", nargs="?", default="accept", help="pandoc --track-changes mode: accept (default) or all")
    args = parser.parse_args()
    src, dst = args.src, args.dst
    mode = args.mode

    import pypandoc

    t0 = time.monotonic()
    md = pypandoc.convert_file(
        src,
        "gfm",
        extra_args=[f"--track-changes={mode}", "--wrap=none"],
    )
    elapsed = time.monotonic() - t0

    Path(dst).write_text(md)
    print(f"elapsed_s={elapsed:.2f} chars={len(md)} mode={mode}", file=sys.stderr)


if __name__ == "__main__":
    main()
