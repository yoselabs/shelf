"""Knowledge: the glossary, living ADRs with frontmatter, and the generated decision index."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint import adr
from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_ADR = """---
id: 0001
title: One gate command
statement: just check is the only gate; CI and hooks run it
concerns: [gate]
status: accepted
decided_by: owner
updated: 2026-10-11
---
# 0001 One gate command

## Decision
just check is the gate.

## History
- 2026-10-11: decided. Rejected: per-tool CI steps, because they drift from the local gate.
"""


def _verdicts(repo: Repo) -> dict[str, tuple[Verdict, str]]:
    return {r.id: (r.verdict, r.evidence) for r in run(repo.root, concern="knowledge", env=repo.env).rows}


def _sound(repo: Repo) -> None:
    repo.write("CONTEXT.md", "# Context\n")
    repo.write("docs/adr/0001-one-gate-command.md", _ADR)
    repo.write("docs/adr/INDEX.md", adr.index(repo.root))


def test_a_sound_record_passes(repo: Repo) -> None:
    _sound(repo)
    assert {v for v, _ in _verdicts(repo).values()} == {Verdict.PASSING}


def test_no_glossary_is_not_set_up(repo: Repo) -> None:
    _sound(repo)
    (repo.root / "CONTEXT.md").unlink()
    assert _verdicts(repo)["knowledge.glossary"][0] is Verdict.NOT_SET_UP


def test_no_adr_folder_is_not_set_up(repo: Repo) -> None:
    repo.write("CONTEXT.md", "# Context\n")
    verdicts = _verdicts(repo)
    assert verdicts["knowledge.adr-format"][0] is Verdict.NOT_SET_UP
    assert verdicts["knowledge.adr-index"][0] is Verdict.NOT_SET_UP


def test_an_adr_without_frontmatter_fails_and_is_named(repo: Repo) -> None:
    _sound(repo)
    repo.write("docs/adr/0002-loose.md", "# ADR 0002 — Loose\n\n**Status:** Accepted\n")
    verdict, evidence = _verdicts(repo)["knowledge.adr-format"]
    assert verdict is Verdict.FAILING
    assert "0002-loose.md" in evidence


def test_an_id_that_differs_from_the_file_number_fails(repo: Repo) -> None:
    _sound(repo)
    repo.write("docs/adr/0002-other.md", _ADR)
    verdict, evidence = _verdicts(repo)["knowledge.adr-format"]
    assert verdict is Verdict.FAILING
    assert "id 0001" in evidence


def test_an_adr_without_a_history_section_fails(repo: Repo) -> None:
    _sound(repo)
    repo.write("docs/adr/0001-one-gate-command.md", _ADR.split("## History", maxsplit=1)[0])
    verdict, evidence = _verdicts(repo)["knowledge.adr-format"]
    assert verdict is Verdict.FAILING
    assert "no ## History" in evidence


def test_the_format_fix_says_how_to_fold_an_amending_adr(repo: Repo) -> None:
    _sound(repo)
    repo.write("docs/adr/0001-one-gate-command.md", _ADR.split("## History", maxsplit=1)[0])
    fix = next(r.remediation for r in run(repo.root, concern="knowledge", env=repo.env).rows if r.id == "knowledge.adr-format")
    assert "amends" in fix
    assert "History" in fix


def test_an_unknown_status_fails(repo: Repo) -> None:
    _sound(repo)
    repo.write("docs/adr/0001-one-gate-command.md", _ADR.replace("status: accepted", "status: maybe"))
    assert _verdicts(repo)["knowledge.adr-format"][0] is Verdict.FAILING


def test_a_stale_index_fails_and_the_generator_fixes_it(repo: Repo) -> None:
    _sound(repo)
    repo.write("docs/adr/0002-hooks.md", _ADR.replace("0001", "0002").replace("One gate command", "Hooks by prek"))
    assert _verdicts(repo)["knowledge.adr-index"][0] is Verdict.FAILING
    repo.write("docs/adr/INDEX.md", adr.index(repo.root))
    assert _verdicts(repo)["knowledge.adr-index"][0] is Verdict.PASSING


def test_the_index_carries_statements_and_leaves_out_superseded(repo: Repo) -> None:
    _sound(repo)
    repo.write("docs/adr/0002-old.md", _ADR.replace("0001", "0002").replace("status: accepted", "status: superseded"))
    text = adr.index(repo.root)
    assert "just check is the only gate; CI and hooks run it" in text
    assert "0002" not in text
    assert "only to challenge" in text
