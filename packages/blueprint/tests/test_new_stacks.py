"""node: a repo set up the profile's way passes every role; the same repo with an empty gate fails the gate-run ones."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from blueprint.concerns.stacks.stack import ROLES
from blueprint.model import Verdict
from blueprint.profile import detect_stacks
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_TYPOS = {"typos.toml": "[default]\n"}
_HOOKS_FILE = ".pre-commit-config.yaml"

_NODE_FILES = {
    "package.json": (
        '{"engines": {"node": ">=24"}, "packageManager": "pnpm@10.0.0", "devDependencies": {"vitest": "3.0.0", "knip": "5.0.0"}}'
    ),
    "pnpm-lock.yaml": "lockfileVersion: 9\n",
    "biome.json": '{"linter": {"enabled": true}}',
    "tsconfig.json": '{"compilerOptions": {"strict": true}}',
    "knip.json": "{}",
    "vitest.config.ts": "export default { test: { coverage: { thresholds: { lines: 90 } } } }",
    ".dependency-cruiser.cjs": "module.exports = { forbidden: [] }",
    "docs/agents/node.md": "node\n",
    "AGENTS.md": "docs/agents/node.md\n",
    _HOOKS_FILE: "biome typos\n",
}
_NODE_STEPS = [
    "pnpm install --frozen-lockfile",
    "biome ci .",
    "tsc --noEmit",
    "knip",
    "vitest run --coverage",
    "depcruise src --config .dependency-cruiser.cjs",
    "typos",
]
_NODE_GATE = "\n".join(_NODE_STEPS)

_STACKS = {
    "node": (_NODE_FILES, _NODE_GATE),
}
_MANIFEST = {"node": "package.json"}


def _set_up(repo: Repo, stack: str, *, gate: bool = True) -> None:
    files, commands = _STACKS[stack]
    for rel, text in {**_TYPOS, **files}.items():
        repo.write(rel, text)
    body = "".join(f"\t{c}\n" for c in commands.splitlines()) if gate else "\ttrue\n"
    repo.write("justfile", f"check:\n{body}")


def _rows(repo: Repo, stack: str) -> dict[str, Verdict]:
    return {r.id: r.verdict for r in run(repo.root, concern="stack", env=repo.env).rows if r.id.startswith(f"stack.{stack}.")}


@pytest.mark.parametrize("stack", sorted(_STACKS))
def test_a_repo_set_up_the_profiles_way_passes_every_role(repo: Repo, stack: str) -> None:
    _set_up(repo, stack)
    rows = _rows(repo, stack)
    assert {f"stack.{stack}.{role}" for role in ROLES} <= rows.keys()
    assert {k: v for k, v in rows.items() if v is not Verdict.PASSING} == {}


@pytest.mark.parametrize("stack", sorted(_STACKS))
def test_the_same_repo_with_a_gate_that_runs_nothing_fails_the_tests_and_architecture_roles(repo: Repo, stack: str) -> None:
    _set_up(repo, stack, gate=False)
    rows = _rows(repo, stack)
    assert rows[f"stack.{stack}.tests"] in {Verdict.FAILING, Verdict.NOT_SET_UP}
    assert rows[f"stack.{stack}.architecture"] in {Verdict.FAILING, Verdict.NOT_SET_UP}


@pytest.mark.parametrize("stack", sorted(_STACKS))
def test_a_repo_with_only_the_manifest_is_not_set_up_on_its_roles(repo: Repo, stack: str) -> None:
    repo.write(_MANIFEST[stack], "{}" if stack == "node" else "x\n")
    rows = _rows(repo, stack)
    assert rows[f"stack.{stack}.formatter"] in {Verdict.FAILING, Verdict.NOT_SET_UP}
    assert rows[f"stack.{stack}.architecture"] is Verdict.NOT_SET_UP


# --- a repo with two stacks (mission task 5): one gate, each stack judged on its own steps, contact through a declared edge ---

_PY_GATE = "lint:\n\tuv lock --check\n\tuv run ruff format --check .\n\tuv run ruff check .\n"
_PYPROJECT = '[project]\nname = "x"\nrequires-python = ">=3.12"\n\n[tool.ruff]\nline-length = 100\n'


def _mixed(repo: Repo, *, node_steps: bool = True, edge: bool = True, contract: bool = True) -> None:
    """Python at the root, Node in web/: one Makefile gate runs both stacks' steps."""
    repo.write("pyproject.toml", _PYPROJECT)
    repo.write("uv.lock", "")
    for rel, text in {**_TYPOS, **_NODE_FILES}.items():
        repo.write(rel if rel in {"typos.toml", ".pre-commit-config.yaml", "AGENTS.md"} or rel.startswith("docs/") else f"web/{rel}", text)
    node_body = "".join(f"\t{c}\n" for c in _NODE_GATE.splitlines()) if node_steps else ""
    repo.write("justfile", f"check: lint web\n{_PY_GATE}web:\n{node_body or chr(9) + 'true' + chr(10)}")
    if contract:
        repo.write("schema/api.json", "{}")
    if edge:
        repo.write(
            "docs/blueprint/blueprint.toml",
            '[[edge]]\nfrom = "node"\nto = "python-uv"\nvia = "schema/api.json"\nreason = "the web client reads the API schema"\n',
        )


def _all_rows(repo: Repo) -> dict[str, Verdict]:
    return {r.id: r.verdict for r in run(repo.root, concern="stack", env=repo.env).rows}


def test_a_node_folder_below_the_root_is_detected_beside_python(repo: Repo) -> None:
    _mixed(repo)
    assert {"python-uv", "node"} <= set(detect_stacks(repo.root))


def test_each_stack_in_one_gate_is_judged_on_its_own_steps(repo: Repo) -> None:
    _mixed(repo)
    rows = _all_rows(repo)
    assert rows["stack.python-uv.formatter"] is Verdict.PASSING
    assert rows["stack.node.tests"] is Verdict.PASSING
    assert rows["stack.node.architecture"] is Verdict.PASSING


def test_dropping_the_node_steps_fails_node_and_leaves_python_alone(repo: Repo) -> None:
    _mixed(repo, node_steps=False)
    rows = _all_rows(repo)
    assert rows["stack.node.tests"] is Verdict.FAILING
    assert rows["stack.node.architecture"] is Verdict.FAILING
    assert rows["stack.python-uv.formatter"] is Verdict.PASSING


def test_a_declared_edge_with_its_contract_file_passes(repo: Repo) -> None:
    _mixed(repo)
    assert _all_rows(repo)["stack.edges"] is Verdict.PASSING


@pytest.mark.parametrize(
    ("source", "target", "verdict"),
    [
        ("node-tooling", "python-uv", Verdict.PASSING),
        ("python-uv", "node-tooling", Verdict.PASSING),
        ("dotnet", "python-uv", Verdict.FAILING),
        ("python-uv", "dotnet", Verdict.FAILING),
    ],
)
def test_python_and_scripts_only_node_edges_resolve_only_present_stacks(repo: Repo, source: str, target: str, verdict: Verdict) -> None:
    # shelf-xgi5: the detected node-tooling name is valid at either end of an edge.
    repo.write("pyproject.toml", _PYPROJECT)
    repo.write("uv.lock", "")
    repo.write("package.json", '{"scripts": {"build": "tailwindcss -i in.css -o out.css"}}')
    repo.write("schema/api.json", "{}")
    repo.write(
        "docs/blueprint/blueprint.toml",
        f'[[edge]]\nfrom = "{source}"\nto = "{target}"\nvia = "schema/api.json"\nreason = "shared schema"\n',
    )
    assert set(detect_stacks(repo.root)) == {"python-uv", "node-tooling"}
    row = next(r for r in run(repo.root, concern="stack", env=repo.env).rows if r.id == "stack.edges")
    assert row.verdict is verdict
    if verdict is Verdict.PASSING:
        assert "not a stack" not in row.evidence
    else:
        assert "names dotnet, not a stack of this repo" in row.evidence


def test_two_code_stacks_with_no_declared_edge_are_not_set_up(repo: Repo) -> None:
    _mixed(repo, edge=False)
    result = run(repo.root, concern="stack", env=repo.env)
    row = next(r for r in result.rows if r.id == "stack.edges")
    assert row.verdict is Verdict.NOT_SET_UP
    assert "[[edge]]" in row.remediation


def test_an_edge_whose_contract_file_is_missing_fails(repo: Repo) -> None:
    _mixed(repo, contract=False)
    row = next(r for r in run(repo.root, concern="stack", env=repo.env).rows if r.id == "stack.edges")
    assert row.verdict is Verdict.FAILING
    assert "schema/api.json" in row.evidence


def test_an_edge_naming_a_stack_the_repo_lacks_fails(repo: Repo) -> None:
    _mixed(repo)
    repo.write("docs/blueprint/blueprint.toml", '[[edge]]\nfrom = "dotnet"\nto = "python-uv"\nvia = "schema/api.json"\nreason = "x"\n')
    row = next(r for r in run(repo.root, concern="stack", env=repo.env).rows if r.id == "stack.edges")
    assert row.verdict is Verdict.FAILING
    assert "dotnet" in row.evidence


def test_a_single_stack_repo_has_no_edges_row(repo: Repo) -> None:
    repo.write("pyproject.toml", _PYPROJECT)
    repo.write("uv.lock", "")
    assert "stack.edges" not in _all_rows(repo)


def test_the_node_spelling_and_hooks_rows_accept_codespell_for_typos(repo: Repo) -> None:
    files = {k: v for k, v in _NODE_FILES.items() if k != "typos.toml"}
    files[_HOOKS_FILE] = "biome codespell\n"
    for rel, text in {**files, ".codespellrc": "[codespell]\nskip = x\n"}.items():
        repo.write(rel, text)
    repo.write("justfile", "check:\n" + "".join(f"\t{c}\n" for c in [*_NODE_STEPS[:-1], "codespell"]))
    rows = _rows(repo, "node")
    assert rows["stack.node.spelling"] is Verdict.PASSING
    assert rows["stack.node.hooks"] is Verdict.PASSING


def test_the_node_spelling_row_still_fails_with_neither_tool_configured(repo: Repo) -> None:
    for rel, text in _NODE_FILES.items():
        repo.write(rel, text)
    rows = _rows(repo, "node")
    assert rows["stack.node.spelling"] is Verdict.NOT_SET_UP


def test_the_node_spelling_and_hooks_rows_accept_blueprints_lint_changed_as_codespell(repo: Repo) -> None:
    files = {k: v for k, v in _NODE_FILES.items() if k != "typos.toml"}
    files[_HOOKS_FILE] = "biome\n  entry: uv run blueprint gate lint --changed\n"
    for rel, text in {**files, ".codespellrc": "[codespell]\nskip = x\n"}.items():
        repo.write(rel, text)
    repo.write("justfile", "check:\n" + "".join(f"\t{c}\n" for c in [*_NODE_STEPS[:-1], "uv run blueprint gate lint --changed"]))
    rows = _rows(repo, "node")
    assert rows["stack.node.spelling"] is Verdict.PASSING
    assert rows["stack.node.hooks"] is Verdict.PASSING


# --- shelf-meqv: the codespell config sits in the Python stack's folder -------------------------------------------------------


def _backend_spell(repo: Repo, spell_paths: str) -> None:
    for rel, text in _NODE_FILES.items():
        repo.write(rel if rel.startswith("docs/") or rel in {"AGENTS.md", _HOOKS_FILE} else f"frontend/{rel}", text)
    repo.write(
        "backend/pyproject.toml",
        f'[project]\nname = "x"\n[tool.codespell]\nskip = "x"\n[tool.blueprint.gate]\nspell-paths = {spell_paths}\n',
    )
    repo.write("backend/uv.lock", "version = 1\n")
    repo.write("compose.yml", "services: {}\n")
    repo.write("justfile", "check:\n\tblueprint gate spell\n")


def _spelling(repo: Repo) -> dict[str, Verdict]:
    return {r.id: r.verdict for r in run(repo.root, concern="stack", env=repo.env).rows if r.id.endswith(".spelling")}


def test_node_and_compose_spelling_accept_the_python_folders_codespell_when_its_paths_reach_them(repo: Repo) -> None:
    _backend_spell(repo, '["src", "../frontend", "../compose.yml"]')
    rows = _spelling(repo)
    assert rows["stack.node.spelling"] is Verdict.PASSING
    assert rows["stack.compose.spelling"] is Verdict.PASSING


def test_node_spelling_fails_when_the_python_folders_spell_paths_miss_the_frontend(repo: Repo) -> None:
    _backend_spell(repo, '["src", "../compose.yml"]')
    rows = _spelling(repo)
    assert rows["stack.node.spelling"] is Verdict.NOT_SET_UP
    assert rows["stack.compose.spelling"] is Verdict.PASSING


def test_compose_spelling_fails_when_the_spell_paths_miss_the_compose_file(repo: Repo) -> None:
    _backend_spell(repo, '["src", "../frontend"]')
    rows = _spelling(repo)
    assert rows["stack.compose.spelling"] is Verdict.NOT_SET_UP


def test_no_spell_paths_means_codespell_reads_only_its_own_folder(repo: Repo) -> None:
    _backend_spell(repo, "[]")
    assert _spelling(repo)["stack.node.spelling"] is Verdict.NOT_SET_UP
