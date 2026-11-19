"""read_rev keeps returning the full sha256 hex of the raw file bytes (revisions must not change)."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from any_json_doc import Doc

if TYPE_CHECKING:
    from pathlib import Path


def test_revision_is_plain_sha256_of_the_raw_bytes(tmp_path: Path) -> None:
    path = tmp_path / "d.json"
    raw = json.dumps({"k": "zażółć"}).encode()
    path.write_bytes(raw)
    _, rev = Doc(path).read_rev()
    assert rev == hashlib.sha256(raw).hexdigest()
