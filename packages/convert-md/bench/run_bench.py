"""Orchestrator: run every engine over every corpus file, capture output + timing.

Every engine runs isolated via `uv run --with <pkg>` (D4) — none is a real
`convert-md` runtime dependency for the format it's probed on. Each engine x
corpus cell gets a generous per-cell timeout so one slow/broken engine doesn't
block the others; a timeout or crash is itself a recorded result, not a hard
failure of the run.

Two formats now (docx-engine-verification, design.md D4): the PDF grid is
unchanged; a docx capability-grid runs the same way over `corpus/docx/*.docx`.
An engine is `(name, install_specs, runner, extra_args, timeout_s)` so pandoc
can appear twice (accept vs all track-changes modes) sharing one runner.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

BENCH_DIR = Path(__file__).parent
CORPUS_DIR = BENCH_DIR / "corpus"
OUTPUTS_DIR = BENCH_DIR / "outputs"
ENGINES_DIR = BENCH_DIR / "engines"


@dataclass(frozen=True)
class Engine:
    name: str  # output label + default runner stem
    specs: tuple[str, ...]  # isolated `uv run --with` package spec(s)
    timeout_s: int
    runner: str = ""  # runner stem override; defaults to `name`
    extra_args: tuple[str, ...] = field(default_factory=tuple)

    def runner_path(self) -> Path:
        return ENGINES_DIR / f"run_{self.runner or self.name}.py"


# PDF grid — unchanged from the pdf-engine-verification work.
_PDF_ENGINES: list[Engine] = [
    Engine("docling", ("docling",), 300),
    Engine("markitdown", ("markitdown[pdf]",), 120),
    Engine("pymupdf4llm", ("pymupdf4llm",), 120),
    Engine("unstructured", ("unstructured[pdf]",), 300),
    Engine("marker", ("marker-pdf",), 1800),  # CPU-only, model download + inference
]

# docx capability-grid (design.md D3). pandoc appears twice, both modes, one runner.
_DOCX_ENGINES: list[Engine] = [
    Engine("pandoc-accept", ("pypandoc-binary",), 120, runner="pandoc", extra_args=("accept",)),
    Engine("pandoc-all", ("pypandoc-binary",), 120, runner="pandoc", extra_args=("all",)),
    Engine("markitdown", ("markitdown[docx]",), 120),
    Engine("mammoth", ("mammoth", "html2text"), 120),
]

_FORMATS: dict[str, list[Engine]] = {
    ".pdf": _PDF_ENGINES,
    ".docx": _DOCX_ENGINES,
}


def _run_one(engine: Engine, src: Path) -> dict:
    out_path = OUTPUTS_DIR / f"{engine.name}__{src.stem}.md"
    with_flags: list[str] = []
    for spec in engine.specs:
        with_flags += ["--with", spec]
    cmd = [
        "uv",
        "run",
        "--no-project",
        *with_flags,
        "python3",
        str(engine.runner_path()),
        str(src),
        str(out_path),
        *engine.extra_args,
    ]

    t0 = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=engine.timeout_s, check=False)
    except subprocess.TimeoutExpired:
        return {"engine": engine.name, "file": src.name, "status": "timeout", "elapsed_s": engine.timeout_s}
    elapsed = time.monotonic() - t0

    if proc.returncode != 0:
        return {
            "engine": engine.name,
            "file": src.name,
            "status": "error",
            "elapsed_s": round(elapsed, 1),
            "stderr_tail": proc.stderr[-2000:],
        }
    return {
        "engine": engine.name,
        "file": src.name,
        "status": "ok",
        "elapsed_s": round(elapsed, 1),
        "output_path": str(out_path.relative_to(BENCH_DIR)),
        "chars": out_path.stat().st_size if out_path.exists() else 0,
    }


def _corpus_for(fmt: str) -> list[Path]:
    if fmt == ".pdf":
        return sorted(CORPUS_DIR.glob("*.pdf"))
    return sorted((CORPUS_DIR / fmt.lstrip(".")).glob(f"*{fmt}"))


def main() -> None:
    """Usage: run_bench.py [format] [engine] [file1,file2]

    format defaults to .pdf (back-compat); pass `.docx` for the docx grid.
    """
    OUTPUTS_DIR.mkdir(exist_ok=True)
    fmt = sys.argv[1] if len(sys.argv) > 1 else ".pdf"
    if not fmt.startswith("."):
        fmt = "." + fmt
    only_engine = sys.argv[2] if len(sys.argv) > 2 else None
    only_files = sys.argv[3].split(",") if len(sys.argv) > 3 else None

    engines = _FORMATS.get(fmt, [])
    corpus = _corpus_for(fmt)
    if only_files:
        corpus = [f for f in corpus if f.name in only_files]

    results = []
    for engine in engines:
        if only_engine and engine.name != only_engine:
            continue
        for src in corpus:
            print(f"--- {engine.name} x {src.name} ---", file=sys.stderr)
            r = _run_one(engine, src)
            print(f"    {r['status']} in {r.get('elapsed_s', '?')}s", file=sys.stderr)
            results.append(r)

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
