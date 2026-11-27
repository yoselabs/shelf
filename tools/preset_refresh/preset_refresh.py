#!/usr/bin/env python3
"""Rewrite the packaged linter preset (blueprint's preset.toml) from this repo's own pyproject.toml and uv.lock. Shelf-only: not shipped."""

from __future__ import annotations

import argparse
from pathlib import Path

from blueprint import preset

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "packages" / "blueprint" / "src" / "blueprint" / "preset.toml"


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    TARGET.write_text(preset.render(preset.snapshot(ROOT)))
    print(f"wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
