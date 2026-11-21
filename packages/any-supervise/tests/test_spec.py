"""The spec file: what it reads and what it refuses."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from any_supervise import SpecError, load_spec

if TYPE_CHECKING:
    from pathlib import Path

HEAD = 'state = "st"\nversion_cmd = ["git", "rev-parse", "HEAD"]\nversion_cwd = "repo"\n'


def spec(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "s.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_relative_paths_resolve_against_the_spec_folder_and_replicas_are_numbered(tmp_path: Path) -> None:
    got = load_spec(spec(tmp_path, HEAD + '[[worker]]\nname = "snap"\ncommand = ["x", "{index}"]\ncount = 3\nlog = "logs"\n'))
    root = tmp_path.resolve()
    assert (got.state, got.version_cwd, got.workers[0].log, got.workers[0].cwd) == (root / "st", root / "repo", root / "logs", root)
    assert [r.name for r in got.replicas] == ["snap-1", "snap-2", "snap-3"]
    assert got.replicas[1].argv == ("x", "2")
    assert got.workers[0].stop_timeout_s == 30.0


@pytest.mark.parametrize(
    "text",
    [
        HEAD,  # no worker
        HEAD + '[[worker]]\nname = "a"\ncommand = ["x"]\nlog = "l"\nbogus = 1\n',
        HEAD + '[[worker]]\nname = "a"\ncommand = []\nlog = "l"\n',
        HEAD + '[[worker]]\nname = "a/b"\ncommand = ["x"]\nlog = "l"\n',
        HEAD + '[[worker]]\nname = "a"\ncommand = ["x"]\ncount = 0\nlog = "l"\n',
        HEAD + '[[worker]]\nname = "a"\ncommand = ["x"]\nlog = "l"\n[[worker]]\nname = "a"\ncommand = ["x"]\nlog = "l"\n',
        HEAD + '[[worker]]\nname = "a"\ncommand = ["x"]\nlog = "l"\n[[worker]]\nname = "a-1"\ncommand = ["x"]\nlog = "l"\n',
        'state = "st"\n[[worker]]\nname = "a"\ncommand = ["x"]\nlog = "l"\n',  # no version_cmd
        "not toml [",
    ],
)
def test_a_bad_spec_is_refused(tmp_path: Path, text: str) -> None:
    with pytest.raises(SpecError):
        load_spec(spec(tmp_path, text))


def test_a_missing_file_is_a_spec_error(tmp_path: Path) -> None:
    with pytest.raises(SpecError):
        load_spec(tmp_path / "none.toml")
