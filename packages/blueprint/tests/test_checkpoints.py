"""`blueprint checkpoints`: every checkpoint, what it checks, and the fact that turns it on."""

from __future__ import annotations

import json

import pytest
from blueprint.__main__ import main


def _rows(capsys: pytest.CaptureFixture[str], *args: str) -> list[dict[str, str]]:
    assert main(["checkpoints", "--json", *args]) == 0
    rows: list[dict[str, str]] = json.loads(capsys.readouterr().out)
    return rows


def test_lists_registered_and_profile_checkpoints_with_their_turning_on_fact(capsys: pytest.CaptureFixture[str]) -> None:
    rows = {r["id"]: r for r in _rows(capsys)}
    assert rows["gate.ci-green"]["turned_on_by"].startswith("always")
    profile_row = rows["stack.dockerfile.linter"]
    assert "dockerfile stack is detected" in profile_row["turned_on_by"]
    assert profile_row["statement"]


def test_the_plain_table_names_the_columns(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["checkpoints", "stack.dockerfile"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].split() == ["ID", "STATEMENT", "TURNED", "ON", "BY"]
    assert "stack.dockerfile.linter" in out


def test_a_prefix_filters_by_id(capsys: pytest.CaptureFixture[str]) -> None:
    ids = [r["id"] for r in _rows(capsys, "stack.dockerfile")]
    assert ids
    assert all(i.startswith("stack.dockerfile") for i in ids)


def test_help_exits_zero_with_a_description(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stop:
        main(["checkpoints", "--help"])
    assert stop.value.code == 0
    assert "checkpoint" in capsys.readouterr().out


def test_an_unknown_flag_exits_two() -> None:
    with pytest.raises(SystemExit) as stop:
        main(["checkpoints", "--nope"])
    assert stop.value.code == 2
