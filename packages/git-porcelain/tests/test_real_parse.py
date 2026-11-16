"""Worktree porcelain records must be complete and preserve literal paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from git_porcelain import GitUnavailable
from git_porcelain.real_parse import parse_cat_file_batch, parse_worktrees

_HEAD = "a" * 40


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        (f"worktree /main\0HEAD {_HEAD}\0branch refs/heads/main\0\0", [(Path("/main"), _HEAD, "main")]),
        (f'worktree /quoted "é"\t\npath\0HEAD {_HEAD}\0detached\0\0', [(Path('/quoted "é"\t\npath'), _HEAD, None)]),
        (f"worktree /raw\udcff\0HEAD {_HEAD}\0detached\0\0", [(Path("/raw\udcff"), _HEAD, None)]),
        ("worktree /bare\0bare\0\0", [(Path("/bare"), None, None)]),
        (f"worktree /main\0HEAD {'0' * 40}\0branch refs/heads/main\0\0", [(Path("/main"), None, "main")]),
        (
            f"worktree /gone\0HEAD {_HEAD}\0detached\0prunable gitdir file points nowhere\0\0",
            [(Path("/gone"), _HEAD, None)],
        ),
    ],
)
def test_worktree_records_preserve_paths(record: str, expected: list[tuple[Path, str | None, str | None]]) -> None:
    assert parse_worktrees(record) == expected


@pytest.mark.parametrize(
    "record",
    [
        "",
        "worktree /partial",
        f"worktree /partial\0HEAD {_HEAD}\0detached\0",
        "worktree /partial\0\0",
        f"worktree /partial\0HEAD {_HEAD}\0\0",
        "worktree /partial\0HEAD invalid\0detached\0\0",
        f"worktree \0HEAD {_HEAD}\0detached\0\0",
        f"HEAD {_HEAD}\0detached\0\0",
        f"worktree /partial\0HEAD {_HEAD}\0HEAD {_HEAD}\0detached\0\0",
        f"worktree /partial\0HEAD {_HEAD}\0branch refs/heads/main\0detached\0\0",
        f"worktree /ok\0HEAD {_HEAD}\0detached\0\0worktree /partial\0",
    ],
)
def test_incomplete_or_malformed_worktree_records_raise(record: str) -> None:
    with pytest.raises(GitUnavailable, match="worktree list"):
        parse_worktrees(record)


@pytest.mark.parametrize(
    ("raw", "count", "expected"),
    [
        (b"", 0, []),
        (b"a1 blob 3\nx\ny\n", 1, [b"x\ny"]),
        (b"HEAD:my file missing\na1 blob 0\n\n", 2, [None, b""]),
        (b"a1 tree 5\n12345\nb2 blob 2\n\xff\n\n", 2, [None, b"\xff\n"]),
        (b"abc ambiguous\n", 1, [None]),
    ],
)
def test_cat_file_batch_records_keep_exact_bytes(raw: bytes, count: int, expected: list[bytes | None]) -> None:
    assert parse_cat_file_batch(raw, count) == expected
