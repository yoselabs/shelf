"""Receipts: a green result remembered under a key of what it ran on, so the same work is never run twice."""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING

import pytest
from any_gate import Receipts, key

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def receipts(tmp_path: Path) -> Receipts:
    return Receipts(tmp_path / "state" / "receipts.json", keep=3)


def test_a_recorded_result_is_remembered_under_its_name_and_key(receipts: Receipts) -> None:
    receipts.record("tests", "k1")
    assert receipts.has("tests", "k1")
    assert not receipts.has("tests", "k2")
    assert not receipts.has("types", "k1")


def test_nothing_is_remembered_before_anything_is_recorded(receipts: Receipts) -> None:
    assert not receipts.has("tests", "k1")


def test_the_oldest_keys_of_a_name_are_forgotten_past_the_keep_limit(receipts: Receipts) -> None:
    for number in range(5):
        receipts.record("tests", f"k{number}")
    assert [receipts.has("tests", f"k{number}") for number in range(5)] == [False, False, True, True, True]


def test_recording_a_key_again_makes_it_the_newest(receipts: Receipts) -> None:
    for name in ("a", "b", "c"):
        receipts.record("tests", name)
    receipts.record("tests", "a")
    receipts.record("tests", "d")
    assert [receipts.has("tests", name) for name in ("a", "b", "c", "d")] == [True, False, True, True]


def test_another_handle_on_the_same_file_sees_a_record(receipts: Receipts, tmp_path: Path) -> None:
    receipts.record("tests", "k1")
    assert Receipts(tmp_path / "state" / "receipts.json").has("tests", "k1")


@pytest.mark.parametrize("damage", ["", "not json", "[1, 2]", '{"receipts": "x"}', '{"receipts": {"tests": "k1"}}'])
def test_a_damaged_file_remembers_nothing_and_is_repaired_by_the_next_record(receipts: Receipts, tmp_path: Path, damage: str) -> None:
    path = tmp_path / "state" / "receipts.json"
    path.parent.mkdir(parents=True)
    path.write_text(damage)
    assert not receipts.has("tests", "k1")
    receipts.record("tests", "k1")
    assert receipts.has("tests", "k1")
    assert json.loads(path.read_text())["receipts"] == {"tests": ["k1"]}


def test_the_file_is_plain_json_a_reader_in_any_language_can_parse(receipts: Receipts, tmp_path: Path) -> None:
    receipts.record("tests", "k1")
    receipts.record("types", "k9")
    assert json.loads((tmp_path / "state" / "receipts.json").read_text()) == {
        "version": 1,
        "receipts": {"tests": ["k1"], "types": ["k9"]},
    }


def test_a_key_is_the_same_whatever_the_order_of_its_parts() -> None:
    assert key(a="1", b="2") == key(b="2", a="1")
    assert key(a="1", b="2") != key(a="1", b="3")


def test_a_key_is_long_enough_that_two_inputs_never_share_one() -> None:
    assert len(key(a="1")) == 32


def test_a_key_refuses_what_json_cannot_say() -> None:
    with pytest.raises(TypeError):
        key(when=dt.datetime.now(tz=dt.UTC))
