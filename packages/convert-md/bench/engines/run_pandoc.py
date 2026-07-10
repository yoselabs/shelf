"""Probe runner: pandoc (via pypandoc-binary), docx -> gfm markdown.

Scored in BOTH track-changes modes (design.md D3) so the bench quantifies
pandoc's sole differentiator instead of assuming it:

    argv[3] = "accept" (default) -> --track-changes=accept  (clean final text)
    argv[3] = "all"              -> --track-changes=all      (renders redlines)

Isolated install (D4): pypandoc-binary is fetched only for the bench, matching
convert-md's real docx invocation (`gfm`, `--wrap=none`).
"""

import sys
import time
from pathlib import Path


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "accept"

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
