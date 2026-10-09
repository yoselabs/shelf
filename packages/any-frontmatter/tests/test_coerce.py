"""Reading a frontmatter value never raises — a malformed one is a miss."""

from __future__ import annotations

import datetime as dt

import pytest
from any_frontmatter import opt_str, str_seq, written_nothing


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Robin Vale", "Robin Vale"),
        (" padded ", " padded "),  # not stripped: the author's spacing is theirs
        (None, None),
        ("", None),
        ([], None),
        ({}, None),
        (0, "0"),  # falsy and present
        (False, "False"),
        (dt.date(2026, 9, 12), "2026-09-12"),
        ([1, 2], "[1, 2]"),  # nonsense in, a string out
    ],
)
def test_opt_str(value: object, expected: str | None) -> None:
    assert opt_str(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (["a", "b"], ("a", "b")),
        (("a", "b"), ("a", "b")),
        ([], ()),
        (None, ()),
        ("solo", ()),  # a bare scalar is not a one-item sequence
        (["a", "", None, "b"], ("a", "b")),
        ([1, 2], ("1", "2")),
        ({"a": 1}, ()),
    ],
)
def test_str_seq(value: object, expected: tuple[str, ...]) -> None:
    assert str_seq(value) == expected


def test_a_value_whose_str_raises_is_a_miss() -> None:
    class Hostile:
        def __str__(self) -> str:
            msg = "boom"
            raise RuntimeError(msg)

    assert opt_str(Hostile()) is None
    assert str_seq([Hostile(), "kept"]) == ("kept",)


@pytest.mark.parametrize(
    ("value", "empty"),
    [(None, True), ("", True), ([], True), ({}, True), (0, False), (False, False), ((), False), (" ", False)],
)
def test_written_nothing_is_the_four_empties(value: object, empty: bool) -> None:
    assert written_nothing(value) is empty
