"""The packaged preset snapshot is derived from the shelf's own files; it must not go stale (a consumer is compared against it)."""

from __future__ import annotations

from pathlib import Path

from blueprint import preset

ROOT = Path(__file__).resolve().parent.parent


def test_the_packaged_preset_matches_the_shelfs_own_config() -> None:
    packaged = (ROOT / "packages" / "blueprint" / "src" / "blueprint" / "preset.toml").read_text()
    assert packaged == preset.render(preset.snapshot(ROOT)), (
        "run `uv run python tools/preset_refresh/preset_refresh.py` and commit preset.toml"
    )
