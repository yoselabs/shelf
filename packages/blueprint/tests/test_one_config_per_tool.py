"""`layout.one-config-per-tool` (ADR 0035): a tool's config is defined once per repo; a project that differs extends the shared base."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_ROW = "layout.one-config-per-tool"
_RUFF = 'line-length = 120\ntarget-version = "py312"\n[lint]\nselect = ["E", "F", "I", "B", "UP"]\nignore = ["E501"]\n'
_TS = '{"compilerOptions": {"strict": true, "target": "es2022", "module": "esnext", "noUnusedLocals": true}}\n'


def _row(repo: Repo):
    return {r.id: r for r in run(repo.root, concern="layout", env=repo.env, today=date(2026, 12, 1)).rows}[_ROW]


def test_two_projects_carrying_the_same_ruff_config_fail_and_name_the_pair_and_extend(repo: Repo) -> None:
    repo.write("backend/ruff.toml", _RUFF)
    repo.write("tools/ruff.toml", _RUFF)
    row = _row(repo)
    assert row.verdict is Verdict.FAILING
    assert "ruff: backend/ruff.toml and tools/ruff.toml" in row.evidence
    assert 'extend = "../ruff.toml"' in row.remediation


def test_a_near_copy_with_one_changed_line_is_still_a_copy(repo: Repo) -> None:
    repo.write("backend/ruff.toml", _RUFF)
    repo.write("tools/ruff.toml", _RUFF.replace("120", "100"))
    assert _row(repo).verdict is Verdict.FAILING


def test_ruff_in_a_pyproject_counts_as_a_definition(repo: Repo) -> None:
    repo.write(
        "backend/pyproject.toml",
        "[project]\nname='a'\n[tool.ruff]\nline-length = 120\ntarget-version = 'py312'\n"
        "[tool.ruff.lint]\nselect = ['E','F','I','B','UP']\nignore = ['E501']\n",
    )
    repo.write("tools/ruff.toml", _RUFF)
    assert _row(repo).verdict is Verdict.FAILING


def test_a_project_that_extends_the_base_carries_only_the_delta_and_passes(repo: Repo) -> None:
    repo.write("ruff.toml", _RUFF)
    repo.write("tools/ruff.toml", 'extend = "../ruff.toml"\n[lint]\nignore = ["S101"]\n')
    assert _row(repo).verdict is Verdict.PASSING


def test_a_second_config_that_differs_a_lot_is_not_a_copy(repo: Repo) -> None:
    repo.write("backend/ruff.toml", _RUFF)
    repo.write("tools/ruff.toml", 'line-length = 88\n[lint]\nselect = ["ALL"]\nfixable = ["ALL"]\n[format]\nquote-style = "single"\n')
    assert _row(repo).verdict is Verdict.PASSING


def test_a_tool_that_cannot_extend_says_waive(repo: Repo) -> None:
    repo.write("a/.hadolint.yaml", "ignored:\n  - DL3008\n  - DL3009\n  - DL3015\n  - DL3018\n")
    repo.write("b/.hadolint.yaml", "ignored:\n  - DL3008\n  - DL3009\n  - DL3015\n  - DL3018\n")
    row = _row(repo)
    assert row.verdict is Verdict.FAILING
    assert "cannot extend: waive" in row.remediation


def test_tsconfig_copies_name_extends(repo: Repo) -> None:
    repo.write("web/tsconfig.json", _TS)
    repo.write("admin/tsconfig.json", _TS)
    row = _row(repo)
    assert row.verdict is Verdict.FAILING
    assert '"extends"' in row.remediation


def test_one_definition_and_fixture_copies_pass(repo: Repo) -> None:
    repo.write("ruff.toml", _RUFF)
    repo.write("tests/fixtures/x/ruff.toml", _RUFF)
    assert _row(repo).verdict is Verdict.PASSING


def test_trivial_configs_are_not_copies(repo: Repo) -> None:
    repo.write("a/tsconfig.json", '{"extends": "../tsconfig.base.json"}\n')
    repo.write("b/tsconfig.json", '{"extends": "../tsconfig.base.json"}\n')
    assert _row(repo).verdict is Verdict.PASSING


def test_a_dated_waiver_passes_the_row(repo: Repo) -> None:
    repo.write("backend/ruff.toml", _RUFF)
    repo.write("tools/ruff.toml", _RUFF)
    repo.write(
        "docs/blueprint/blueprint.toml",
        f'[[tool.blueprint.waivers]]\nid = "{_ROW}"\nreason = "the projects split next quarter"\n'
        f'since = "2026-12-01"\nuntil = "2026-12-31"\n',
    )
    assert _row(repo).verdict is Verdict.PASSING
