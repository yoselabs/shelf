"""Recorded exchanges replay as stable golden cases."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from any_recorded_fixture import (
    Case,
    GoldenMismatchError,
    cases,
    golden,
    read_json,
    record,
    scrub,
    update_requested,
    write_json,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_record_round_trip(tmp_path: Path) -> None:
    meta: dict[str, object] = {"model": "test", "unicode": "é"}
    directory = record(tmp_path, "chat", "hello", {"request.json": {"messages": []}}, meta, text={"input.txt": "héllo\n"})
    assert cases(tmp_path) == [Case("chat", "hello", directory, meta)]
    assert read_json(directory / "request.json") == {"messages": []}
    assert (directory / "input.txt").read_text(encoding="utf-8") == "héllo\n"
    assert read_json(directory / "meta.json") == meta
    write_json(directory / "response.json", [1, None])
    assert (directory / "response.json").read_text(encoding="utf-8") == "[\n 1,\n null\n]\n"
    assert read_json(directory / "response.json") == [1, None]


def test_cases_are_sorted_and_require_metadata(tmp_path: Path) -> None:
    assert cases(tmp_path / "absent") == []
    for group, case in [("z", "a"), ("a", "z"), ("a", "b")]:
        record(tmp_path, group, case, {}, {})
    (tmp_path / "a" / "ignored").mkdir()
    (tmp_path / "a" / "file").write_text("ignored", encoding="utf-8")
    (tmp_path / "file").write_text("ignored", encoding="utf-8")
    assert [(item.group, item.case) for item in cases(tmp_path)] == [("a", "b"), ("a", "z"), ("z", "a")]


def test_golden_pass_fail_and_update(tmp_path: Path) -> None:
    path = tmp_path / "input.txt"
    golden(path, "before\n", update=True)
    golden(path, "before\n", update=False)
    with pytest.raises(GoldenMismatchError) as error:
        golden(path, "after\n", update=False)
    assert isinstance(error.value, AssertionError)
    for fragment in ["---", "+++", "@@", "-before", "+after"]:
        assert fragment in str(error.value)
    assert path.read_text(encoding="utf-8") == "before\n"
    golden(path, "after\n", update=True)
    golden(path, "after\n", update=False)


def test_missing_golden_has_diff(tmp_path: Path) -> None:
    path = tmp_path / "missing.txt"
    with pytest.raises(GoldenMismatchError) as error:
        golden(path, "actual\n", update=False)
    assert "missing" in str(error.value).lower()
    assert "+actual" in str(error.value)
    assert not path.exists()
    with pytest.raises(GoldenMismatchError):
        golden(path, "", update=False)


def test_scrub_longest_first() -> None:
    assert scrub("/w/x/file /w/x /w/x/file", wt="/w/x", file="/w/x/file", empty="") == "<FILE> <WT> <FILE>"
    assert scrub("unchanged") == "unchanged"


@pytest.mark.parametrize(
    ("env", "expected"),
    [({}, False), ({"FLAG": ""}, False), ({"FLAG": "0"}, False), ({"FLAG": "1"}, True), ({"FLAG": "false"}, True)],
)
def test_update_requested(env: dict[str, str], expected: bool) -> None:
    assert update_requested(env, "FLAG") is expected


def test_update_requested_default_name() -> None:
    assert update_requested({"UPDATE_GOLDEN": "yes"})
