"""try_claim: one unit per free-form key, flock only."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

import pytest

from any_lease import Leases
from any_lease._keyfile import keyfile

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def leases(tmp_path: Path) -> Leases:
    return Leases(tmp_path / "locks")


def test_a_claimed_key_is_refused_to_a_second_claim_until_released(leases: Leases) -> None:
    held = leases.try_claim("model/UCxxxx", label="model")
    assert held is not None
    assert leases.try_claim("model/UCxxxx") is None
    held.release()
    again = leases.try_claim("model/UCxxxx")
    assert again is not None
    again.release()


def test_leaving_the_with_block_releases(leases: Leases) -> None:
    held = leases.try_claim("k")
    assert held is not None
    with held:
        assert leases.try_claim("k") is None
    free = leases.try_claim("k")
    assert free is not None
    free.release()


def test_keys_that_differ_only_by_unsafe_characters_stay_distinct(leases: Leases) -> None:
    one, two = leases.try_claim("a/b"), leases.try_claim("a_b")
    assert one is not None
    assert two is not None
    one.release()
    two.release()


def test_claiming_many_keys_makes_no_limit_file_and_records_the_holder(leases: Leases) -> None:
    held = [leases.try_claim(f"model/UC{i}", label="model", meta={"n": i}) for i in range(1400)]
    try:
        assert all(h is not None for h in held)
        files = [p for p in leases.root.rglob("*") if p.is_file()]
        assert not [p for p in files if p.suffix == ".limit"]
        assert len(files) == 1400  # one lock file per key, all flat under one folder
        assert {p.parent for p in files} == {leases.root / "claims"}
        record = json.loads(next(p for p in files).read_text())
        assert record["label"] == "model"
    finally:
        for h in held:
            if h is not None:
                h.release()


def test_an_empty_key_is_refused(leases: Leases) -> None:
    with pytest.raises(ValueError, match="empty"):
        leases.try_claim("")


def test_keyfile_name_is_the_old_sha256_name() -> None:
    """The stored `claims/` and `.pace` names must not move when the hash moved to content-digest."""
    assert keyfile("model/UC1") == f"model_UC1-{hashlib.sha256(b'model/UC1').hexdigest()[:16]}"
