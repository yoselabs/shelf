"""The literal ignore rule: one exact path, nothing a glob could add."""

from __future__ import annotations

import pytest

from git_porcelain.ignore_rules import literal_pattern


@pytest.mark.parametrize(
    ("path", "rule"),
    [
        ("a/b.txt", "/a/b.txt"),
        ("build/", "/build/"),
        ("we*ird[1]?.x", "/we\\*ird\\[1]\\?.x"),
        ("#hash", "/\\#hash"),
        ("!bang", "/\\!bang"),
        ("back\\slash", "/back\\\\slash"),
        ("pad  ", "/pad\\ \\ "),
    ],
)
def test_literal_pattern_escapes_what_git_would_read_as_syntax(path: str, rule: str) -> None:
    assert literal_pattern(path) == rule
