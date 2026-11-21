"""A package.json that only runs build tools is its own stack: the TypeScript and test rows say why they do not apply; the rest warn."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from blueprint.model import Verdict
from blueprint.profile import detect_stacks
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_BUILD: dict[str, Any] = {"scripts": {"ui-css": "tailwindcss -i in.css -o out.css"}, "devDependencies": {"tailwindcss": "4.0.0"}}


def _stack(repo: Repo, manifest: dict[str, Any]) -> str:
    repo.write("package.json", json.dumps(manifest))
    stacks = {s for s in detect_stacks(repo.root) if s.startswith("node")}
    assert len(stacks) == 1
    return stacks.pop()


def test_a_manifest_that_only_builds_is_node_tooling(repo: Repo) -> None:
    assert _stack(repo, _BUILD) == "node-tooling"


@pytest.mark.parametrize(
    "manifest",
    [
        {},
        {"scripts": {}},
        {**_BUILD, "scripts": {**_BUILD["scripts"], "test": "vitest run"}},
        {**_BUILD, "scripts": {"typecheck": "tsc --noEmit"}},
        {**_BUILD, "devDependencies": {"typescript": "5.0.0"}},
        {**_BUILD, "devDependencies": {"vitest": "3.0.0"}},
    ],
    ids=["no-fields", "no-scripts", "test-script", "tsc-script", "typescript-dep", "vitest-dep"],
)
def test_anything_that_tests_or_type_checks_stays_node(repo: Repo, manifest: dict[str, Any]) -> None:
    assert _stack(repo, manifest) == "node"


def test_a_tsconfig_beside_it_keeps_it_node(repo: Repo) -> None:
    repo.write("tsconfig.json", "{}")
    assert _stack(repo, _BUILD) == "node"


def _rows(repo: Repo) -> dict[str, tuple[Verdict, str]]:
    return {
        r.id: (r.verdict, r.evidence) for r in run(repo.root, concern="stack", env=repo.env).rows if r.id.startswith("stack.node-tooling.")
    }


def test_the_typescript_and_test_runner_rows_do_not_apply_and_say_why(repo: Repo) -> None:
    repo.write("package.json", json.dumps(_BUILD))
    rows = _rows(repo)
    assert "stack.node-tooling.coverage" not in rows  # a role the profile marks not applicable and that is cut makes no row at all
    for role, word in (("types", "TypeScript"), ("tests", "runner")):
        verdict, evidence = rows[f"stack.node-tooling.{role}"]
        assert verdict is Verdict.NOT_APPLICABLE
        assert word in evidence


def test_the_rows_the_profile_still_asks_for_do_not_pass_on_a_bare_manifest(repo: Repo) -> None:
    repo.write("package.json", json.dumps(_BUILD))
    rows = _rows(repo)
    for role in ("formatter", "linter", "dependencies", "architecture"):
        assert rows[f"stack.node-tooling.{role}"][0] in {Verdict.NOT_SET_UP, Verdict.FAILING}


_SET_UP = {
    "package.json": json.dumps(
        {
            "engines": {"node": ">=24"},
            "packageManager": "pnpm@10.0.0",
            "scripts": {"ui-css": "tailwindcss -i in.css -o out.css"},
            "devDependencies": {"tailwindcss": "4.0.0", "knip": "5.0.0"},
        }
    ),
    "pnpm-lock.yaml": "lockfileVersion: 9\n",
    "biome.json": '{"linter": {"enabled": true}}',
    "knip.json": "{}",
    "typos.toml": "[default]\n",
    ".dependency-cruiser.cjs": "module.exports = { forbidden: [] }",
    ".pre-commit-config.yaml": "biome typos\n",
    "docs/agents/node.md": "node\n",
    "AGENTS.md": "docs/agents/node.md\n",
    "Makefile": (
        "check:\n\tpnpm install --frozen-lockfile\n\tbiome ci .\n\tknip\n\tdepcruise src --config .dependency-cruiser.cjs\n\ttypos\n"
    ),
}


def test_a_repo_set_up_the_profiles_way_has_no_row_that_is_not_passing_or_not_applicable(repo: Repo) -> None:
    for rel, text in _SET_UP.items():
        repo.write(rel, text)
    assert {s for s in detect_stacks(repo.root) if s.startswith("node")} == {"node-tooling"}
    rows = _rows(repo)
    assert {k: v for k, (v, _) in rows.items() if v not in {Verdict.PASSING, Verdict.NOT_APPLICABLE}} == {}
    assert rows["stack.node-tooling.toolchain"][0] is Verdict.PASSING
