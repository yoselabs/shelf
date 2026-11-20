"""Onboarding reconciles a consumer's existing shelf git sources instead of writing a pyproject that cannot lock (shelf-mw91).

a2kay pinned `anyllm-v0.8.1` for several shelf packages and `atomic-io-v0.1.0`; `any-gate` needs `atomic-io>=0.2`, and uv reported
conflicting git sources. Onboarding stops there, naming the sources that must move together, and writes nothing.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from onboard.hooks import ShelfSourceConflict, ensure_gate_dependency
from onboard.linter_preset import LinterPresetOperation
from onboard.operations import Outcome

_URL = "https://github.com/yoselabs/shelf"
_A2KAY_LIKE = f"""\
[project]
name = "a2kay"
version = "0.1.0"
dependencies = ["anyllm", "atomic-io", "stream-proc"]

[dependency-groups]
dev = ["ruff"]

[tool.uv.sources]
anyllm = {{ git = "{_URL}", subdirectory = "packages/anyllm", tag = "anyllm-v0.8.1" }}
atomic-io = {{ git = "{_URL}", subdirectory = "packages/atomic-io", tag = "atomic-io-v0.1.0" }}
stream-proc = {{ git = "{_URL}", subdirectory = "packages/stream-proc", tag = "anyllm-v0.8.1" }}
"""


def _repo(tmp_path: Path, text: str) -> Path:
    (tmp_path / "pyproject.toml").write_text(text)
    return tmp_path


def test_an_old_shelf_source_the_kit_cannot_lock_with_stops_and_names_the_sources_to_move_together(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _A2KAY_LIKE)
    with pytest.raises(ShelfSourceConflict) as stop:
        ensure_gate_dependency(repo)
    message = str(stop.value)
    assert "atomic-io" in message
    assert "atomic-io-v0.1.0" in message
    assert "any-gate" in message
    assert "anyllm" in message, "every shelf source of the repo moves with it: they come from one snapshot"
    assert "snapshot" in message
    assert (repo / "pyproject.toml").read_text() == _A2KAY_LIKE, "never write a pyproject that cannot lock"


def test_the_linter_preset_operation_stops_before_writing_anything(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _A2KAY_LIKE)
    result = LinterPresetOperation(repo).run({})
    assert result.outcome == Outcome.COULD_NOT_APPLY
    assert "atomic-io-v0.1.0" in result.message
    assert (repo / "pyproject.toml").read_text() == _A2KAY_LIKE
    assert not (repo / ".blueprint").exists()
    assert not (repo / "justfile").exists()


def test_a_source_that_satisfies_what_the_kit_needs_is_kept(tmp_path: Path) -> None:
    text = _A2KAY_LIKE.replace("atomic-io-v0.1.0", "atomic-io-v0.2.0")
    repo = _repo(tmp_path, text)
    ensure_gate_dependency(repo)
    sources = tomllib.loads((repo / "pyproject.toml").read_text())["tool"]["uv"]["sources"]
    assert sources["atomic-io"]["tag"] == "atomic-io-v0.2.0"
    assert sources["anyllm"]["tag"] == "anyllm-v0.8.1"
    assert "any-gate" in sources


def test_a_different_spelling_of_the_shelf_url_is_reused_with_no_second_source(tmp_path: Path) -> None:
    spelled = "https://github.com/yoselabs/shelf.git"
    text = (
        '[project]\nname = "c"\nversion = "0.1.0"\n\n[tool.uv.sources]\n'
        f'atomic-io = {{ git = "{spelled}", subdirectory = "packages/atomic-io", tag = "atomic-io-v0.2.0" }}\n'
    )
    repo = _repo(tmp_path, text)
    ensure_gate_dependency(repo)
    sources = tomllib.loads((repo / "pyproject.toml").read_text())["tool"]["uv"]["sources"]
    assert {s["git"] for s in sources.values() if "git" in s} == {spelled}
    assert sources["any-gate"]["git"] == spelled
    assert "override-dependencies" not in (repo / "pyproject.toml").read_text()


def test_a_non_shelf_source_is_not_mistaken_for_one(tmp_path: Path) -> None:
    text = '[project]\nname = "c"\nversion = "0.1.0"\n\n[tool.uv.sources]\natomic-io = { path = "../atomic-io" }\n'
    repo = _repo(tmp_path, text)
    ensure_gate_dependency(repo)
    assert tomllib.loads((repo / "pyproject.toml").read_text())["tool"]["uv"]["sources"]["atomic-io"] == {"path": "../atomic-io"}
