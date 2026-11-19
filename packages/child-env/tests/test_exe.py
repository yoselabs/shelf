from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from child_env import Exe, NotFound, find

if TYPE_CHECKING:
    from pathlib import Path


def _tool(folder: Path, name: str = "tool", *, mode: int = 0o755) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(mode)
    return path


def test_finds_on_the_path_of_the_injected_env(tmp_path: Path) -> None:
    tool = _tool(tmp_path / "bin")
    assert find("tool", {"PATH": str(tmp_path / "bin")}) == Exe(path=tool, how="path")


def test_first_path_entry_wins(tmp_path: Path) -> None:
    first = _tool(tmp_path / "a")
    _tool(tmp_path / "b")
    assert find("tool", {"PATH": f"{tmp_path / 'a'}:{tmp_path / 'b'}"}).path == first


def test_path_beats_extra_dirs(tmp_path: Path) -> None:
    on_path = _tool(tmp_path / "a")
    _tool(tmp_path / "b")
    exe = find("tool", {"PATH": str(tmp_path / "a")}, extra_dirs=[tmp_path / "b"])
    assert exe == Exe(path=on_path, how="path")


def test_extra_dir_is_searched_after_the_path(tmp_path: Path) -> None:
    tool = _tool(tmp_path / "extra")
    exe = find("tool", {"PATH": str(tmp_path / "empty")}, extra_dirs=[tmp_path / "extra"])
    assert exe == Exe(path=tool, how="extra_dir")


def test_ambient_path_is_never_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ambient = tmp_path / "ambient"
    _tool(ambient)
    monkeypatch.setenv("PATH", str(ambient))
    with pytest.raises(NotFound):
        find("tool", {})


def test_missing_binary_raises_naming_what_was_searched(tmp_path: Path) -> None:
    searched = [str(tmp_path / "a"), str(tmp_path / "b")]
    with pytest.raises(NotFound) as caught:
        find("tool", {"PATH": searched[0]}, extra_dirs=[tmp_path / "b"])
    assert caught.value.name == "tool"
    assert caught.value.searched == tuple(searched)
    assert "tool" in str(caught.value)
    assert all(s in str(caught.value) for s in searched)


def test_not_found_is_a_lookup_error() -> None:
    assert issubclass(NotFound, LookupError)


def test_a_file_without_the_execute_bit_is_not_found(tmp_path: Path) -> None:
    _tool(tmp_path / "bin", mode=0o644)
    with pytest.raises(NotFound):
        find("tool", {"PATH": str(tmp_path / "bin")})


def test_a_directory_with_the_name_is_not_found(tmp_path: Path) -> None:
    (tmp_path / "bin" / "tool").mkdir(parents=True)
    with pytest.raises(NotFound):
        find("tool", {"PATH": str(tmp_path / "bin")})


def test_empty_path_entries_are_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(_tool(tmp_path / "cwd").parent)  # an empty entry would mean the working folder
    with pytest.raises(NotFound) as caught:
        find("tool", {"PATH": ":"})
    assert caught.value.searched == ()


def test_a_name_with_a_separator_is_refused(tmp_path: Path) -> None:
    tool = _tool(tmp_path)
    with pytest.raises(ValueError, match="bare name"):
        find(str(tool), {"PATH": str(tmp_path)})
