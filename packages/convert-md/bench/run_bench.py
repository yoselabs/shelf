"""Orchestrator: run every engine over every corpus PDF, capture output + timing.

Every engine runs isolated via `uv run --with <pkg>` (D4) — none is a real
`convert-md` PDF dependency: docling was dropped from the package entirely
in v0.5.0 (design.md D5) but stays probed here so future re-verification is
still possible; markitdown is a real `documents`-extra dependency for other
formats, but its `[pdf]` extra isn't declared there, so it's probed isolated
too, same as every other engine. Each engine x corpus cell gets a generous
per-cell timeout so one slow/broken engine doesn't block the others; a
timeout or crash is itself a recorded result, not a hard failure of the run.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

BENCH_DIR = Path(__file__).parent
CORPUS_DIR = BENCH_DIR / "corpus"
OUTPUTS_DIR = BENCH_DIR / "outputs"
ENGINES_DIR = BENCH_DIR / "engines"

# (engine name, isolated extra package spec) — every engine is probed isolated
# (D4); none of these specs are declared in convert-md's own pyproject.toml.
# markitdown IS a real convert-md[documents] dependency, but only its base install
# — the [pdf] sub-extra isn't declared (convert-md only ever routes markitdown to
# pptx/xlsx, see dispatch.py) — so it's probed the same way as every other engine.
_ENGINES: list[tuple[str, str]] = [
    ("docling", "docling"),
    ("markitdown", "markitdown[pdf]"),
    ("pymupdf4llm", "pymupdf4llm"),
    ("unstructured", "unstructured[pdf]"),
    ("marker", "marker-pdf"),
]

_TIMEOUT_S = {
    "docling": 300,
    "markitdown": 120,
    "pymupdf4llm": 120,
    "unstructured": 300,
    "marker": 1800,  # CPU-only, model download + inference — generous
}


def _run_one(engine: str, spec: str, pdf: Path) -> dict:
    out_path = OUTPUTS_DIR / f"{engine}__{pdf.stem}.md"
    runner = ENGINES_DIR / f"run_{engine}.py"
    cmd = ["uv", "run", "--no-project", "--with", spec, "python3", str(runner), str(pdf), str(out_path)]

    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S[engine],
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"engine": engine, "pdf": pdf.name, "status": "timeout", "elapsed_s": _TIMEOUT_S[engine]}
    elapsed = time.monotonic() - t0

    if proc.returncode != 0:
        return {
            "engine": engine,
            "pdf": pdf.name,
            "status": "error",
            "elapsed_s": round(elapsed, 1),
            "stderr_tail": proc.stderr[-2000:],
        }
    return {
        "engine": engine,
        "pdf": pdf.name,
        "status": "ok",
        "elapsed_s": round(elapsed, 1),
        "output_path": str(out_path.relative_to(BENCH_DIR)),
        "chars": out_path.stat().st_size if out_path.exists() else 0,
    }


def main() -> None:
    OUTPUTS_DIR.mkdir(exist_ok=True)
    corpus = sorted(CORPUS_DIR.glob("*.pdf"))
    only_engine = sys.argv[1] if len(sys.argv) > 1 else None
    only_files = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    if only_files:
        corpus = [pdf for pdf in corpus if pdf.name in only_files]

    results = []
    for engine, spec in _ENGINES:
        if only_engine and engine != only_engine:
            continue
        for pdf in corpus:
            print(f"--- {engine} x {pdf.name} ---", file=sys.stderr)
            r = _run_one(engine, spec, pdf)
            print(f"    {r['status']} in {r.get('elapsed_s', '?')}s", file=sys.stderr)
            results.append(r)

    import json

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
