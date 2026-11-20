"""lint_path reports a directory's files in sorted order, whatever order the file system lists them."""

from pathlib import Path

import pytest
from a2effect import lint


def test_a_directory_is_linted_in_sorted_path_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("b.py", "a.py", "c.py"):
        (tmp_path / name).write_text("x = 1\n", encoding="utf-8")
    seen: list[str] = []

    def rule(_tree: object, *, path: Path, source: str) -> list[object]:
        seen.append(path.name)
        return []

    monkeypatch.setattr(lint, "discover_rules", lambda: {"R": rule})
    listed = [tmp_path / n for n in ("c.py", "a.py", "b.py")]
    monkeypatch.setattr(Path, "rglob", lambda _self, _pattern: iter(listed))

    lint.lint_path(tmp_path)

    assert seen == ["a.py", "b.py", "c.py"]
