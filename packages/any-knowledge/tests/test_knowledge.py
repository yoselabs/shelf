"""any_knowledge: the ADR checks, the index, the glossary and the seeded agent docs, through the CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from any_knowledge import adr, templates
from any_knowledge.cli import main

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_ADR = """---
id: 0001
title: One gate command
statement: just check is the only gate
concerns: [gate]
status: accepted
decided_by: owner
updated: 2026-10-11
---
# 0001 One gate command

## History
- 2026-10-11: decided.
"""


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "docs/adr").mkdir(parents=True)
    (tmp_path / "docs/adr/0001-one-gate-command.md").write_text(_ADR)
    (tmp_path / "docs/adr/INDEX.md").write_text(adr.index(tmp_path))
    return tmp_path


def _check(repo: Path, *extra: str) -> int:
    return main(["check", "--repo", str(repo), *extra])


def test_a_sound_record_passes(tmp_path: Path) -> None:
    assert _check(_repo(tmp_path)) == 0


def test_a_repo_without_adrs_is_not_judged(tmp_path: Path) -> None:
    assert _check(tmp_path) == 0


def test_a_malformed_adr_fails_naming_it(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _repo(tmp_path)
    (repo / "docs/adr/0002-bad.md").write_text("no frontmatter\n")
    assert _check(repo) == 1
    assert "0002-bad.md: no frontmatter" in capsys.readouterr().err


def test_a_stale_index_fails_and_index_write_repairs_it(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "docs/adr/INDEX.md").write_text("old\n")
    assert _check(repo) == 1
    assert main(["index", "--repo", str(repo), "--write"]) == 0
    assert _check(repo) == 0


def test_the_glossary_is_required_only_when_asked(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert _check(repo) == 0
    assert _check(repo, "--glossary") == 1
    (repo / "CONTEXT.md").write_text("# Context\n")
    assert _check(repo, "--glossary") == 0


def test_seed_copies_what_is_missing_never_overwrites_and_keeps_the_block(tmp_path: Path) -> None:
    assert main(["seed", "--repo", str(tmp_path), "--stack", "python-uv", "--beads"]) == 0
    assert (tmp_path / "docs/agents/python.md").is_file()
    assert (tmp_path / "docs/agents/issue-tracker.md").is_file()
    (tmp_path / "docs/agents/gate.md").write_text("mine\n")
    assert templates.install(tmp_path, templates.Selection(("python-uv",), (), beads=True)) == []
    assert (tmp_path / "docs/agents/gate.md").read_text() == "mine\n"
    assert templates.BEGIN in (tmp_path / "AGENTS.md").read_text()
