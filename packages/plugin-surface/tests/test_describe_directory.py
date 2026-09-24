"""describe_directory — list plugin files without importing them."""

from __future__ import annotations

from typing import TYPE_CHECKING

from plugin_surface import describe_directory, describe_file

if TYPE_CHECKING:
    from pathlib import Path

_NAME = "__plugin__"


def _write(directory: Path, name: str, source: str) -> Path:
    path = directory / name
    path.write_text(source, encoding="utf-8")
    return path


def test_reads_the_literal_and_the_top_level_functions(tmp_path: Path) -> None:
    path = _write(tmp_path, "a.py", '__plugin__ = {"name": "a", "limit": 3}\n\ndef run(ctx): ...\nasync def helper(): ...\n')
    got = describe_file(path, declaration=_NAME)
    assert got.problem is None
    assert got.declaration == {"name": "a", "limit": 3}
    assert got.functions == frozenset({"run", "helper"})


def test_an_annotated_declaration_is_read_too(tmp_path: Path) -> None:
    # `NAME: dict = {...}` is an AnnAssign; reading only Assign made annotating the
    # declaration silently un-discover the plugin.
    path = _write(tmp_path, "a.py", 'from typing import Any\n__plugin__: dict[str, Any] = {"name": "a"}\n')
    assert describe_file(path, declaration=_NAME).declaration == {"name": "a"}


def test_the_file_is_never_executed(tmp_path: Path) -> None:
    marker = tmp_path / "ran"
    path = _write(tmp_path, "a.py", f'open({str(marker)!r}, "w").write("x")\n__plugin__ = {{}}\n')
    assert describe_file(path, declaration=_NAME).declaration == {}
    assert not marker.exists()


def test_a_computed_value_is_reported_not_evaluated(tmp_path: Path) -> None:
    marker = tmp_path / "ran"
    path = _write(tmp_path, "a.py", f'__plugin__ = {{"x": open({str(marker)!r}, "w").write("x")}}\n')
    got = describe_file(path, declaration=_NAME)
    assert got.problem == "not_literal"
    assert got.declaration is None
    assert not marker.exists()


def test_each_problem_is_a_value_not_an_exception(tmp_path: Path) -> None:
    cases = {
        "missing.py": ("def run(ctx): ...\n", "missing"),
        "syntax.py": ("def (:\n", "unparsable"),
        "nul.py": ("x = 1\x00\n", "unparsable"),
        "list.py": ("__plugin__ = [1, 2]\n", "not_mapping"),
        "unhashable.py": ("__plugin__ = {[1]: 2}\n", "not_literal"),
    }
    for name, (source, _) in cases.items():
        _write(tmp_path, name, source)
    (tmp_path / "binary.py").write_bytes(b"\xff\xfe\x00bad")

    got = {d.path.name: d.problem for d in describe_directory(tmp_path, declaration=_NAME)}

    assert got == {name: problem for name, (_, problem) in cases.items()} | {"binary.py": "unreadable"}


def test_one_bad_file_does_not_hide_the_others(tmp_path: Path) -> None:
    _write(tmp_path, "a_good.py", '__plugin__ = {"name": "good"}\n')
    _write(tmp_path, "b_bad.py", "def (:\n")
    _write(tmp_path, "c_good.py", '__plugin__ = {"name": "also"}\n')
    names = [d.declaration["name"] for d in describe_directory(tmp_path, declaration=_NAME) if d.declaration]
    assert names == ["good", "also"]


def test_functions_are_known_even_without_a_declaration(tmp_path: Path) -> None:
    # A consumer reporting "missing declaration" vs "missing entrypoint" needs both.
    path = _write(tmp_path, "a.py", "def run(ctx): ...\n")
    got = describe_file(path, declaration=_NAME)
    assert got.problem == "missing"
    assert got.functions == frozenset({"run"})


def test_a_missing_directory_is_empty(tmp_path: Path) -> None:
    assert describe_directory(tmp_path / "absent", declaration=_NAME) == []


def test_results_are_sorted_and_filtered_by_pattern(tmp_path: Path) -> None:
    for name in ("b.py", "a.py", "notes.txt"):
        _write(tmp_path, name, "__plugin__ = {}\n")
    assert [d.path.name for d in describe_directory(tmp_path, declaration=_NAME)] == ["a.py", "b.py"]
