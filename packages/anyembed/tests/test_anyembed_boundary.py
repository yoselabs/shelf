"""Boundary guard: anyembed must not import a2kay (kept reusable)."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from importlib.metadata import requires
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src" / "anyembed"


def test_anyembed_imports_no_a2kay() -> None:
    offenders: list[str] = []
    for py in _SRC.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders += [f"{py.name}: import {a.name}" for a in node.names if a.name.split(".")[0] in {"a2kay", "a2effect", "a2kit"}]
            elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in {"a2kay", "a2effect", "a2kit"}:
                offenders.append(f"{py.name}: from {node.module}")
    assert not offenders, f"anyembed must stay host-agnostic; found: {offenders}"


_NO_TORCH = """
import sys
for name in ("torch", "transformers"):
    sys.modules[name] = None  # an import of it raises ImportError: the [transformers] extra is absent
import anyembed
from anyembed import AnyEmbedError, EmbeddingCache, LlamaCppEmbedder, LocalEmbedder
from anyembed.testing import HashEmbedder
cache = EmbeddingCache(sys.argv[1])
assert cache.embed("hash", ["a"], HashEmbedder(4).embed_documents)
try:
    LocalEmbedder(model_name="BAAI/bge-small-en-v1.5", dim=384).embed_query("q")
except AnyEmbedError as exc:
    print(exc)
assert "torch" not in sys.modules or sys.modules["torch"] is None
"""


def test_imports_and_the_llamacpp_side_need_no_torch(tmp_path: Path) -> None:
    # Only LocalEmbedder needs torch/transformers, and only when it loads; everything else imports
    # and runs without them, so a consumer of `anyembed[llamacpp]` can leave them out of its image.
    run = subprocess.run(
        [sys.executable, "-c", _NO_TORCH, str(tmp_path / "cache.sqlite")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    assert "anyembed[transformers]" in run.stdout


def test_torch_and_transformers_are_only_in_the_transformers_extra() -> None:
    heavy = [r for r in requires("anyembed") or [] if re.split(r"[<>=!~;\[ ]", r, maxsplit=1)[0] in {"torch", "transformers"}]
    assert len(heavy) == 2, heavy
    assert all(r.replace("'", '"').endswith('extra == "transformers"') for r in heavy), heavy
