"""The `resolver-block` operation (D5) — marker-delimited projection into
AGENTS.md, never a pasted copy that can drift undetected.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "tools"))

import onboard.resolver_block as rb  # noqa: E402  -- path-injected, after sys.path setup
from onboard.operations import Outcome  # noqa: E402
from onboard.resolver_block import BLOCK_TEXT, ResolverBlockOperation  # noqa: E402


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    return r


def test_writes_agents_md_when_absent(repo: Path) -> None:
    result = ResolverBlockOperation(repo).run({})

    assert result.outcome == Outcome.APPLIED
    assert result.verified
    written = (repo / "AGENTS.md").read_text()
    assert BLOCK_TEXT in written


def test_second_run_is_a_no_op_when_current(repo: Path) -> None:
    ResolverBlockOperation(repo).run({})
    before = (repo / "AGENTS.md").stat().st_mtime_ns

    result = ResolverBlockOperation(repo).run({})

    assert result.outcome == Outcome.APPLIED
    assert (repo / "AGENTS.md").stat().st_mtime_ns == before, "no-op run must not touch the file"


def test_rewrites_in_place_when_the_source_text_changed(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ResolverBlockOperation(repo).run({})
    monkeypatch.setattr(rb, "BLOCK_TEXT", "a NEW resolver block body")

    result = rb.ResolverBlockOperation(repo).run({})

    assert result.outcome == Outcome.APPLIED
    updated = (repo / "AGENTS.md").read_text()
    assert "a NEW resolver block body" in updated
    assert BLOCK_TEXT not in updated


def test_appends_outside_a_pre_existing_managed_block(repo: Path) -> None:
    (repo / "AGENTS.md").write_text("# Project\n\n<!-- BEGIN OTHER TOOL -->\nsome other tool's content\n<!-- END OTHER TOOL -->\n")

    ResolverBlockOperation(repo).run({})

    content = (repo / "AGENTS.md").read_text()
    other_start = content.index("<!-- BEGIN OTHER TOOL -->")
    other_end = content.index("<!-- END OTHER TOOL -->")
    ours_start = content.index("BEGIN SHELF RESOLVER BLOCK")
    assert ours_start > other_end, "our block landed inside/before another tool's managed region"
    assert "some other tool's content" in content[other_start:other_end]


def test_preserves_a_symlinked_claude_md_pointing_at_agents_md(repo: Path) -> None:
    (repo / "AGENTS.md").write_text("# Project\n")
    (repo / "CLAUDE.md").symlink_to("AGENTS.md")

    result = ResolverBlockOperation(repo).run({})

    assert result.outcome == Outcome.APPLIED
    assert (repo / "CLAUDE.md").is_symlink(), "the symlink must survive, not be replaced by a plain file"
    assert (repo / "CLAUDE.md").resolve() == (repo / "AGENTS.md").resolve()
    assert BLOCK_TEXT in (repo / "AGENTS.md").read_text()
    assert BLOCK_TEXT in (repo / "CLAUDE.md").read_text()


def test_writes_claude_md_when_only_that_exists(repo: Path) -> None:
    (repo / "CLAUDE.md").write_text("# Project\n")

    ResolverBlockOperation(repo).run({})

    assert BLOCK_TEXT in (repo / "CLAUDE.md").read_text()
    assert not (repo / "AGENTS.md").exists()
