"""One-off: run fidelity.grade() against every bench output, print the verdicts.

Not part of the harness proper (run_bench.py) — a throwaway calibration check
answering "are grade()'s thresholds actually reasonable, or just plausible-
looking numbers nobody verified?" (design.md-adjacent question, not a D-numbered
decision). Read-only, no dependency on convert_md's real engines running.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from convert_md.fidelity import grade

BENCH_DIR = Path(__file__).parent
CORPUS_DIR = BENCH_DIR / "corpus"
OUTPUTS_DIR = BENCH_DIR / "outputs"

rows = []
for out_path in sorted(OUTPUTS_DIR.glob("*.md")):
    engine, _, stem = out_path.stem.partition("__")
    pdf_path = CORPUS_DIR / f"{stem}.pdf"
    if not pdf_path.exists():
        continue
    markdown = out_path.read_text(encoding="utf-8", errors="replace")
    source_size = pdf_path.stat().st_size
    fidelity, lost, warnings = grade(markdown=markdown, source_size=source_size, check_yield=False)
    rows.append(
        {
            "engine": engine,
            "doc": stem,
            "fidelity": fidelity,
            "lost": lost,
            "warnings": warnings,
            "out_chars": len(markdown),
            "source_bytes": source_size,
        }
    )

print(json.dumps(rows, indent=2))
