"""A consumer holds an ordered, deduplicated set of path globs."""

from __future__ import annotations

from any_path_glob import Glob, GlobSet


def test_set_preserves_first_glob_and_filters_in_input_order() -> None:
    first = Glob("src/**")
    globs = GlobSet(item for item in [first, "**/*.py", "src/**", Glob("**/*.py")])
    assert list(globs) == [first, Glob("**/*.py")]
    assert len(globs) == 2
    assert globs.first("src/x.py") is first
    assert globs.first("test.py") == Glob("**/*.py")
    assert globs.first("README") is None
    assert globs.matches("src/data.json")
    assert "test.py" in globs
    assert "README" not in globs
    assert 123 not in globs
    paths = ["test.py", "README", "src/data.json", "test.py"]
    assert globs.filter(iter(paths)) == ["test.py", "src/data.json", "test.py"]


def test_empty_set_matches_nothing() -> None:
    globs = GlobSet([])
    assert len(globs) == 0
    assert list(globs) == []
    assert globs.first("") is None
    assert not globs.matches("")
    assert "" not in globs
    assert globs.filter(["", "a"]) == []
