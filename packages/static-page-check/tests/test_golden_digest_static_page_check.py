"""pin_problems keeps comparing the file's full sha256 hex with the pin, and reports it unchanged."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from static_page_check import pin_problems

if TYPE_CHECKING:
    from pathlib import Path


def test_pin_matches_plain_sha256_and_a_mismatch_reports_it(tmp_path: Path) -> None:
    data = bytes(range(256)) * 5
    (tmp_path / "v.js").write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    assert pin_problems(tmp_path, {"v.js": sha}) == []
    assert pin_problems(tmp_path, {"v.js": sha.upper()}) == []
    bad = "0" * 64
    assert pin_problems(tmp_path, {"v.js": bad}) == [
        f"v.js: sha256 {sha} is not the pinned {bad}; replace the file with a new pin, never edit it",
    ]
