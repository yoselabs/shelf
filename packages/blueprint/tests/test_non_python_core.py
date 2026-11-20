"""The core holds no Python assumption (shelf-51yk, design addendum of blueprint-multi-stack-contracts).

A Node repo must be read from its own manifest and its own scripts: never silently empty, never a silent pass.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from blueprint.facts import detect_facts
from blueprint.model import Context, Verdict
from blueprint.profile import detect, load_state
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_PACKAGE = {"name": "x", "dependencies": {"express": "4.19.0"}, "devDependencies": {"openai": "4.0.0"}, "bin": {"x": "cli.js"}}


def _node(repo: Repo, recipe: str, package: dict[str, object] | None = None) -> None:
    repo.write("package.json", json.dumps(package or _PACKAGE))
    repo.write("package-lock.json", "{}")
    repo.write("tools/check.js", "")
    repo.write("justfile", f"check: guard\nguard:\n    {recipe}\n")


def _guards(repo: Repo) -> tuple[Verdict, str]:
    row = next(r for r in run(repo.root, concern="gate", env=repo.env).rows if r.id == "gate.guards-have-red-tests")
    return row.verdict, row.evidence


@pytest.mark.parametrize(
    "recipe", ["node tools/check.js", "node --no-warnings tools/check.js", "npx tsx tools/check.js", "bun tools/check.js"]
)
def test_a_node_guard_script_without_a_test_fails_instead_of_passing_silently(repo: Repo, recipe: str) -> None:
    _node(repo, recipe)
    verdict, evidence = _guards(repo)
    assert verdict is Verdict.FAILING
    assert "tools/check.js" in evidence


@pytest.mark.parametrize("test_file", ["tools/check.test.js", "tests/check.spec.ts", "tests/check.test.mjs"])
def test_a_node_guard_script_a_test_names_passes(repo: Repo, test_file: str) -> None:
    _node(repo, "node tools/check.js")
    repo.write(test_file, "// plants a violation, runs check\n")
    assert _guards(repo)[0] is Verdict.PASSING


def test_a_gate_with_no_repo_script_still_does_not_apply(repo: Repo) -> None:
    repo.write("package.json", json.dumps(_PACKAGE))
    repo.write("justfile", "check:\n    true\n")
    assert _guards(repo)[0] is Verdict.NOT_APPLICABLE


def _detected(repo: Repo) -> tuple[set[str], set[str]]:
    repo.commit()
    facts, evidence = detect_facts(Context(repo.root, detect(repo.root, load_state(repo.root))))
    return {f.claim for f in facts}, {e.claim for e in evidence}


def test_a_package_json_bin_is_a_cli_fact_and_runtime_dependencies_are_evidence(repo: Repo) -> None:
    _node(repo, "true")
    facts, evidence = _detected(repo)
    assert "cli" in facts
    assert "http-server" in evidence  # express, a runtime dependency
    assert "llm-backed" not in evidence  # openai is a devDependency


def test_the_node_surface_reaches_the_profile(repo: Repo) -> None:
    _node(repo, "true")
    repo.commit()
    assert "cli" in run(repo.root, env=repo.env).profile.surfaces


def test_a_node_workspace_without_a_bin_is_a_library(repo: Repo) -> None:
    repo.write("package.json", json.dumps({"name": "x", "workspaces": ["packages/*"]}))
    repo.write("package-lock.json", "{}")
    repo.commit()
    assert run(repo.root, env=repo.env).profile.kind == "library"


def test_a_python_repo_is_read_as_before(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "x"\ndependencies = ["fastapi"]\n\n[project.scripts]\nx = "x:main"\n')
    repo.write("uv.lock", "")
    facts, evidence = _detected(repo)
    assert "cli" in facts
    assert "http-server" in evidence


def _pins(repo: Repo) -> str:
    row = next(r for r in run(repo.root, concern="stack", env=repo.env).rows if r.id == "stack.tool-pins")
    return row.evidence


def test_tool_pins_come_from_the_profile_not_a_stack_name(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    repo.write("uv.lock", "")
    assert "uv (uv.lock)" in _pins(repo)  # python-uv's profile says it runs uv, proved by uv.lock
    repo.root.joinpath("pyproject.toml").unlink()
    repo.root.joinpath("uv.lock").unlink()
    repo.write("package.json", json.dumps(_PACKAGE))
    assert "uv (" not in _pins(repo)


def _one_command(repo: Repo) -> str:
    row = next(r for r in run(repo.root, concern="gate", env=repo.env).rows if r.id == "gate.one-command")
    return row.remediation


def test_the_remediation_comes_from_the_stack_profile(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    repo.write("uv.lock", "")
    assert "blueprint init" in _one_command(repo)
    repo.root.joinpath("pyproject.toml").unlink()
    repo.root.joinpath("uv.lock").unlink()
    repo.write("package.json", json.dumps(_PACKAGE))
    assert "onboard" not in _one_command(repo)
