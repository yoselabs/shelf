"""Probe runner: mammoth -> HTML -> html2text markdown.

This mirrors the *lightest* candidate docx path (design.md D3): mammoth
(featherweight; its only dep is `cobble`) converts docx to semantic HTML, then
convert-md's own existing HTML-chain tail (`html2text`) turns that into
markdown. No new heavy dependency — reuses substrate the base install already
carries. mammoth renders the accepted final text (no tracked-changes support),
same as markitdown, which wraps mammoth internally.
"""

import sys
import time
from pathlib import Path


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]

    import html2text
    import mammoth

    t0 = time.monotonic()
    with Path(src).open("rb") as fh:
        html = mammoth.convert_to_html(fh).value
    converter = html2text.HTML2Text()
    converter.body_width = 0  # no hard wrapping, match pandoc --wrap=none
    md = converter.handle(html)
    elapsed = time.monotonic() - t0

    Path(dst).write_text(md)
    print(f"elapsed_s={elapsed:.2f} chars={len(md)}", file=sys.stderr)


if __name__ == "__main__":
    main()
