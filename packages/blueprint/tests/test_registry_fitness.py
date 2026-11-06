"""The fitness plugin's judging: what it requires, allows and refuses (the plugin itself runs over the whole suite)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tools import blueprint_fitness as fit

if TYPE_CHECKING:
    from pathlib import Path


def test_a_checkpoint_seen_both_ways_is_fit() -> None:
    assert fit.judge([("a", "passing"), ("a", "failing"), ("b", "passing"), ("b", "not set up")], ["a", "b"], set()) == []


def test_a_missing_direction_is_named() -> None:
    problems = fit.judge([("a", "passing")], ["a"], set())
    assert len(problems) == 1
    assert "a: never seen adverse" in problems[0]


def test_unchecked_and_not_applicable_prove_nothing() -> None:
    problems = fit.judge([("a", "not checked"), ("a", "not applicable")], ["a"], set())
    assert len(problems) == 2


def test_a_known_gap_is_allowed_until_the_suite_covers_it() -> None:
    gaps = {("a", "adverse")}
    assert fit.judge([("a", "passing")], ["a"], gaps) == []
    stale = fit.judge([("a", "passing"), ("a", "failing")], ["a"], gaps)
    assert len(stale) == 1
    assert "now covers it" in stale[0]


def test_a_gap_naming_no_required_checkpoint_is_refused() -> None:
    problems = fit.judge([], [], {("ghost", "passing")})
    assert len(problems) == 1
    assert "ghost" in problems[0]


def test_a_gap_needs_a_bead_a_direction_and_no_twin(tmp_path: Path) -> None:
    path = tmp_path / "gaps.toml"
    path.write_text(
        '[[gap]]\nid = "a"\ndirection = "passing"\nbead = "shelf-1"\n'
        '[[gap]]\nid = "a"\ndirection = "passing"\nbead = "shelf-1"\n'
        '[[gap]]\nid = "b"\ndirection = "passing"\n'
        '[[gap]]\nid = "c"\ndirection = "sideways"\nbead = "shelf-2"\n',
        encoding="utf-8",
    )
    _gaps, problems = fit.load_gaps(path)
    assert len(problems) == 3


def test_the_shipped_gaps_file_is_well_formed() -> None:
    _gaps, problems = fit.load_gaps()
    assert problems == []
