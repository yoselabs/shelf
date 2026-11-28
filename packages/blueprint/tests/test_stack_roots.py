"""Stack roots (ADR 0034): a stack is found at the repo root or one folder down, judged with its own profile, and rendered to run there."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from blueprint.runner import run

if TYPE_CHECKING:
    from pathlib import Path

    from blueprint.testing import Repo

_PYPROJECT = '[project]\nname = "app"\nversion = "0"\nrequires-python = ">=3.12"\n'
_TS_PACKAGE = json.dumps({"name": "web", "scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "1", "typescript": "5"}})
_TOOL_PACKAGE = json.dumps({"name": "css", "scripts": {"build": "tailwindcss -o out.css"}, "devDependencies": {"tailwindcss": "4"}})


def _python(repo: Repo, folder: str = "") -> None:
    repo.write(f"{folder}pyproject.toml", _PYPROJECT)
    repo.write(f"{folder}uv.lock", "version = 1\n")


def _profile(repo: Repo):
    return run(repo.root, concern="stack", env=repo.env).profile


def test_a_single_python_stack_at_the_root_is_rooted_at_the_repo(repo: Repo) -> None:
    _python(repo)
    profile = _profile(repo)
    assert profile.stacks == ("python-uv",)
    assert dict(profile.stack_roots)["python-uv"] == "."
    assert dict(profile.stack_files)["python-uv"] == "pyproject.toml, uv.lock"


def test_backend_and_frontend_are_two_stacks_each_with_its_folder(repo: Repo) -> None:
    _python(repo, "backend/")
    repo.write("frontend/package.json", _TS_PACKAGE)
    repo.write("frontend/package-lock.json", "{}")
    profile = _profile(repo)
    assert set(profile.stacks) == {"python-uv", "node"}
    assert dict(profile.stack_roots) == {"python-uv": "backend", "node": "frontend"}
    assert dict(profile.stack_files)["python-uv"] == "backend/pyproject.toml, backend/uv.lock"


def test_root_python_with_a_node_folder_keeps_python_at_the_root(repo: Repo) -> None:
    _python(repo)
    repo.write("ui/package.json", _TS_PACKAGE)
    repo.write("ui/package-lock.json", "{}")
    assert dict(_profile(repo).stack_roots) == {"python-uv": ".", "node": "ui"}


def test_a_lone_node_tool_at_the_root_is_the_node_tooling_stack(repo: Repo) -> None:
    _python(repo)
    repo.write("package.json", _TOOL_PACKAGE)
    assert dict(_profile(repo).stack_roots) == {"python-uv": ".", "node-tooling": "."}


@pytest.mark.parametrize("folder", ["packages/lib/", "tests/fixtures/sample/", "node_modules/dep/", ".venv/lib/", "examples/", "fixtures/"])
def test_workspace_members_fixtures_and_dependencies_are_not_stack_roots(repo: Repo, folder: str) -> None:
    repo.write("README.md", "x\n")
    _python(repo, folder)
    assert _profile(repo).stacks == ()


def test_a_root_manifest_wins_over_one_in_a_folder(repo: Repo) -> None:
    _python(repo)
    _python(repo, "backend/")
    assert dict(_profile(repo).stack_roots)["python-uv"] == "."


def test_two_python_folders_are_two_projects_not_a_backend(repo: Repo) -> None:
    _python(repo, "proxy-api/")
    _python(repo, "health-checker/")
    assert _profile(repo).stacks == ()


_CONFIG = (
    '[project]\nname = "app"\nversion = "0"\nrequires-python = ">=3.12"\n'
    '[tool.ruff]\nline-length = 100\n[tool.ruff.lint]\nselect = ["ALL"]\n'
    '[tool.pyrefly]\nproject-includes = ["src"]\n[tool.codespell]\nskip = "x"\n'
    '[tool.pytest.ini_options]\naddopts = "--strict-markers"\n'
)
_GATE = "lint:\n\tuv run blueprint gate lint\ntypecheck:\n\tuv run pyrefly check\ncheck: lint typecheck\n\tuv lock --check\n"


def _stack_verdicts(repo: Repo, folder: str) -> dict[str, str]:
    prefix = "" if folder == "." else f"{folder}/"
    repo.write(f"{prefix}pyproject.toml", _CONFIG)
    repo.write(f"{prefix}uv.lock", "version = 1\n")
    repo.write(f"{prefix}.python-version", "3.12\n")
    repo.write("justfile", _GATE)
    rows = run(repo.root, concern="stack", env=repo.env).rows
    return {r.id: r.verdict.value for r in rows if r.id.startswith("stack.python-uv.")}


def test_a_python_stack_in_backend_is_judged_as_it_is_at_the_root(repo: Repo, tmp_path: Path) -> None:
    from blueprint.testing import Repo as Fresh  # noqa: PLC0415 -- a second repo in the same test

    (tmp_path / "second").mkdir()

    at_root = _stack_verdicts(repo, ".")
    below = _stack_verdicts(Fresh.create(tmp_path / "second" / "repo", tmp_path / "second" / "bin"), "backend")
    assert at_root == below
    assert {"passing", "not set up"} <= set(at_root.values()), at_root
