"""`layout.stacks-in-own-folders` (ADR 0034): two code bases means backend/ and frontend/, never one of them at the root."""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_ROW = "layout.stacks-in-own-folders"
_TS = json.dumps({"name": "web", "scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "1", "typescript": "5"}})
_TOOL = json.dumps({"name": "css", "scripts": {"build": "tailwindcss -o out.css"}, "devDependencies": {"tailwindcss": "4"}})


def _python(repo: Repo, folder: str = "") -> None:
    repo.write(f"{folder}pyproject.toml", '[project]\nname = "app"\nversion = "0"\nrequires-python = ">=3.12"\n')
    repo.write(f"{folder}uv.lock", "version = 1\n")
    repo.write(f"{folder}src/app/__init__.py", "")
    repo.write(f"{folder}tests/test_app.py", "")


def _node(repo: Repo, folder: str, package: str = _TS) -> None:
    prefix = "" if folder == "." else f"{folder}/"
    repo.write(f"{prefix}package.json", package)
    repo.write(f"{prefix}package-lock.json", "{}")


def _row(repo: Repo):
    rows = {r.id: r for r in run(repo.root, concern="layout", env=repo.env, today=date(2026, 12, 1)).rows}
    return rows[_ROW]


def test_one_code_base_at_the_root_passes(repo: Repo) -> None:
    _python(repo)
    assert _row(repo).verdict is Verdict.PASSING


def test_a_node_tool_beside_the_one_code_base_passes(repo: Repo) -> None:
    _python(repo)
    _node(repo, ".", _TOOL)
    row = _row(repo)
    assert row.verdict is Verdict.PASSING, row.evidence


def test_backend_and_frontend_folders_pass(repo: Repo) -> None:
    _python(repo, "backend/")
    _node(repo, "frontend")
    assert _row(repo).verdict is Verdict.PASSING


def test_python_at_the_root_with_a_ui_folder_fails_and_names_both_moves(repo: Repo) -> None:
    _python(repo)
    _node(repo, "ui")
    row = _row(repo)
    assert row.verdict is Verdict.FAILING
    assert "git mv ui frontend" in row.remediation
    assert "git mv pyproject.toml uv.lock src tests backend/" in row.remediation
    assert "python-uv at the repo root" in row.evidence
    assert "node in ui/" in row.evidence


def test_python_at_the_root_with_frontend_fails_naming_only_the_python_move(repo: Repo) -> None:
    _python(repo)
    _node(repo, "frontend")
    row = _row(repo)
    assert row.verdict is Verdict.FAILING
    assert "git mv pyproject.toml uv.lock src tests backend/" in row.remediation
    assert row.remediation.count("git mv") == 1


def test_two_code_bases_at_the_root_fail(repo: Repo) -> None:
    _python(repo)
    _node(repo, ".")
    row = _row(repo)
    assert row.verdict is Verdict.FAILING
    assert "frontend/" in row.remediation
    assert "git mv package.json package-lock.json frontend/" in row.remediation


def test_a_node_app_nested_two_folders_down_or_hidden_is_no_code_base_of_this_repo(repo: Repo) -> None:
    _python(repo)
    _node(repo, "labs/juice-shop")
    _node(repo, ".opencode")
    row = _row(repo)
    assert row.verdict is Verdict.PASSING, row.evidence


def test_a_repo_with_no_code_base_has_no_layout_to_judge(repo: Repo) -> None:
    repo.write("README.md", "docs only\n")
    assert _row(repo).verdict is Verdict.NOT_APPLICABLE


def test_a_dated_waiver_passes_the_row(repo: Repo) -> None:
    _python(repo)
    _node(repo, "ui")
    repo.write(
        "docs/blueprint/blueprint.toml",
        f'[[tool.blueprint.waivers]]\nid = "{_ROW}"\nreason = "moves with the a2kay split"\nsince = "2026-12-01"\nuntil = "2026-12-31"\n',
    )
    row = _row(repo)
    assert row.verdict is Verdict.PASSING
    assert "waived until 2026-12-31" in row.evidence
