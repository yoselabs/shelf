"""`blueprint gate render` for a node stack: the `ui-*` steps, each rendered only for the tool whose config the folder commits.

The recipes are what a2kay wrote by hand (Biome, tsc, knip, dependency-cruiser, vitest, one locked `npm ci`); the tool is the repo's
choice, read from its config file, never hard-coded: no `biome.json`, no `ui-lint`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tomllib
from typing import TYPE_CHECKING

import pytest
from blueprint import render
from blueprint.model import Verdict
from blueprint.runner import run_audit

if TYPE_CHECKING:
    from blueprint.testing import Repo

PACKAGE = '{"name":"ui","scripts":{"test":"vitest run --coverage"},"devDependencies":{"vitest":"1"}}'
ALL_CONFIG = {
    "biome.json": "{}",
    "tsconfig.json": '{"compilerOptions":{"strict":true}}',
    "knip.json": "{}",
    ".dependency-cruiser.cjs": "module.exports = {}",
}


def _node(repo: Repo, folder: str = "ui", lock: str = "package-lock.json", config: dict[str, str] | None = None) -> None:
    prefix = "" if folder == "." else f"{folder}/"
    repo.write(f"{prefix}package.json", PACKAGE)
    repo.write(f"{prefix}{lock}", "")
    for name, text in (ALL_CONFIG if config is None else config).items():
        repo.write(f"{prefix}{name}", text)


def _steps(repo: Repo) -> list[str]:
    base = render.parts(repo.root)[".blueprint/base.just"]
    line = next(line for line in base.splitlines() if line.startswith("check:"))
    return re.findall(r'"([\w-]+)"', line.split("(steps ", 1)[1].split(")", 1)[0])


def test_a_node_folder_with_every_config_renders_the_five_steps_and_the_install(repo: Repo) -> None:
    _node(repo)
    parts = render.parts(repo.root)
    assert ".blueprint/node.just" in parts
    node = parts[".blueprint/node.just"]
    for recipe in ("ui-install", "ui-lint", "ui-types", "ui-deps", "ui-arch", "ui-test"):
        assert f"\n{recipe}:" in node or f"\n{recipe}: " in node
    assert {"ui-lint", "ui-types", "ui-deps", "ui-arch", "ui-test"} <= set(_steps(repo))
    assert "ui-install" not in _steps(repo)


def test_each_recipe_runs_its_tool_in_the_folder_with_the_pinned_binary(repo: Repo) -> None:
    _node(repo)
    node = render.parts(repo.root)[".blueprint/node.just"]
    assert "cd ui && npx --no-install biome ci --error-on-warnings ." in node
    assert "cd ui && npx --no-install tsc --noEmit" in node
    assert "cd ui && npx --no-install knip" in node
    assert "cd ui && npx --no-install depcruise *.js --config .dependency-cruiser.cjs" in node
    assert "cd ui && npx --no-install vitest run --coverage" in node


def test_the_install_takes_an_atomic_mkdir_lock_so_parallel_steps_install_once(repo: Repo) -> None:
    _node(repo)
    node = render.parts(repo.root)[".blueprint/node.just"]
    assert "until mkdir ui/.node-install.lock" in node
    assert "cd ui && npm ci --no-audit --no-fund" in node
    assert "ui-install" in node.split("\nui-lint:")[1].split("\n")[0]  # the step depends on it


@pytest.mark.parametrize("missing", ["biome.json", "tsconfig.json", "knip.json", ".dependency-cruiser.cjs"])
def test_a_step_is_rendered_only_for_a_tool_the_folder_configures(repo: Repo, missing: str) -> None:
    _node(repo, config={k: v for k, v in ALL_CONFIG.items() if k != missing})
    step = {"biome.json": "ui-lint", "tsconfig.json": "ui-types", "knip.json": "ui-deps", ".dependency-cruiser.cjs": "ui-arch"}[missing]
    assert step not in _steps(repo)
    assert f"\n{step}:" not in render.parts(repo.root)[".blueprint/node.just"]


def test_knip_in_package_json_counts_as_its_config(repo: Repo) -> None:
    _node(repo, config={})
    repo.write("ui/package.json", '{"knip":{},"devDependencies":{"vitest":"1"}}')
    assert "ui-deps" in _steps(repo)


def test_a_pnpm_lock_runs_the_tools_through_pnpm(repo: Repo) -> None:
    _node(repo, lock="pnpm-lock.yaml")
    node = render.parts(repo.root)[".blueprint/node.just"]
    assert "cd ui && pnpm exec biome ci" in node
    assert "cd ui && pnpm install --frozen-lockfile" in node


def test_a_node_repo_with_no_lockfile_renders_no_node_steps(repo: Repo) -> None:
    repo.write("ui/package.json", PACKAGE)
    repo.write("ui/biome.json", "{}")
    assert ".blueprint/node.just" not in render.parts(repo.root)


def test_the_defaults_name_the_folder_and_mise(repo: Repo) -> None:
    _node(repo)
    table = tomllib.loads(render.parts(repo.root)[render.INPUTS_PART])
    for step in ("ui-lint", "ui-types", "ui-deps", "ui-arch", "ui-test"):
        assert table[step] == ["ui/*", "mise.*"]


def test_a_node_folder_at_the_repo_root_has_no_cd_and_no_narrow_default(repo: Repo) -> None:
    _node(repo, folder=".")
    parts = render.parts(repo.root)
    assert "npx --no-install biome ci --error-on-warnings ." in parts[".blueprint/node.just"]
    assert "cd ." not in parts[".blueprint/node.just"]
    assert tomllib.loads(parts[render.INPUTS_PART])["ui-lint"] == ["*"]


def test_a_depcruise_target_is_src_when_the_folder_has_one(repo: Repo) -> None:
    _node(repo)
    repo.write("ui/src/a.ts", "export {}")
    assert "depcruise src --config" in render.parts(repo.root)[".blueprint/node.just"]


@pytest.mark.skipif(shutil.which("just") is None, reason="just is not installed")
def test_the_rendered_node_part_is_valid_just_and_the_repo_stays_current(repo: Repo) -> None:
    _node(repo)
    render.write(repo.root)
    done = subprocess.run(["just", "--list"], cwd=repo.root, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    assert "ui-lint" in done.stdout
    assert render.check(repo.root) == 0


def _audit_rows(repo: Repo, prefix: str) -> dict[str, Verdict]:
    return {r.id: r.verdict for r in run_audit(repo.root, env=repo.env).rows if r.id.startswith(prefix)}


def test_the_stack_node_rows_accept_what_the_render_wrote(repo: Repo) -> None:
    _node(repo)
    repo.write(
        "ui/package.json",
        '{"name":"ui","engines":{"node":">=24"},"packageManager":"npm@11.0.0",'
        '"scripts":{"test":"vitest run --coverage"},"devDependencies":{"vitest":"1","typescript":"5","@vitest/coverage-v8":"1"}}',
    )
    repo.write("ui/vitest.config.js", "export default { test: { coverage: { thresholds: { lines: 80 } } } }")
    repo.write("ui/biome.json", '{"linter":{"enabled":true}}')
    render.write(repo.root)
    rows = _audit_rows(repo, "stack.node.")
    judged = {
        k: v
        for k, v in rows.items()
        if k.split(".")[-1] in {"toolchain", "formatter", "linter", "types", "dependencies", "tests", "coverage", "architecture"}
    }
    assert judged
    assert {k: v for k, v in judged.items() if v is not Verdict.PASSING} == {}
