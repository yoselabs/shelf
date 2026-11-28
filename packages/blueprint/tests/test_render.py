"""`blueprint gate render`: the justfile parts the blueprint owns, written per detected stack, and the drift check on them.

The repo's own `justfile` imports `.blueprint/*.just` and fills the named extension points; a recipe it defines itself wins over
the base one (`set allow-duplicate-recipes`, chosen over `mod` in ADR 0029).
"""

from __future__ import annotations

import shutil
import subprocess
import tomllib
from typing import TYPE_CHECKING

import pytest
from blueprint import render
from blueprint.__main__ import main
from blueprint.concerns.gate import gate_inputs

if TYPE_CHECKING:
    from pathlib import Path

    from blueprint.testing import Repo

needs_just = pytest.mark.skipif(shutil.which("just") is None, reason="just is not installed")


def _python(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    repo.write("uv.lock", "")


def _python_and_shell(repo: Repo) -> None:
    _python(repo)
    repo.write("tools/run.sh", "#!/usr/bin/env bash\n" + "echo hi\n" * 10)


def _just(repo: Repo, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["just", *args], cwd=repo.root, capture_output=True, text=True, check=False)


def test_a_python_repo_gets_the_base_and_the_python_part(repo: Repo) -> None:
    _python(repo)
    parts = render.parts(repo.root)
    assert sorted(parts) == [".blueprint/base.just", ".blueprint/python.just", ".blueprint/step-inputs.toml"]
    assert '"lint-changed" "typecheck"' in parts[".blueprint/base.just"]
    assert "\ntypecheck:" in parts[".blueprint/python.just"]


def test_two_stacks_render_two_parts_and_the_check_names_both_steps(repo: Repo) -> None:
    _python_and_shell(repo)
    parts = render.parts(repo.root)
    assert sorted(parts) == [".blueprint/base.just", ".blueprint/python.just", ".blueprint/shell.just", ".blueprint/step-inputs.toml"]
    assert '"scripts"' in parts[".blueprint/base.just"]


def test_every_repo_gets_the_secret_scan_step_and_its_recipes(repo: Repo) -> None:
    base = render.parts(repo.root)[".blueprint/base.just"]
    assert '"blueprint" "secrets"' in base
    assert "\nsecrets:\n    uv run python -m blueprint.secret_scan range" in base
    assert "\nsecrets-all:" not in base


def test_a_repo_with_no_known_stack_gets_only_the_base(repo: Repo) -> None:
    assert sorted(render.parts(repo.root)) == [".blueprint/base.just", ".blueprint/step-inputs.toml"]


def test_rendering_is_deterministic(repo: Repo) -> None:
    _python_and_shell(repo)
    assert render.parts(repo.root) == render.parts(repo.root)


@pytest.mark.parametrize("folder", ["", "web/", "apps/web/"])
@pytest.mark.parametrize(
    ("lock", "command"),
    [
        ("package-lock.json", "npm ci --no-audit --no-fund"),
        ("pnpm-lock.yaml", "pnpm install --frozen-lockfile"),
        ("yarn.lock", "yarn install --immutable"),
        ("", ""),
    ],
)
def test_tools_installs_in_detected_node_folder_using_its_lock(repo: Repo, folder: str, lock: str, command: str) -> None:
    repo.write(folder + "package.json", '{"scripts": {"build": "vite build"}}')
    if lock:
        repo.write(folder + lock, "")
    tools = render.parts(repo.root)[".blueprint/base.just"].split("\ntools:\n", 1)[1].split("\n\n", 1)[0]
    lines = tools.splitlines()[2:]
    expected = f"cd {folder.rstrip('/')} && {command}" if folder else command
    assert lines == ([f"    {expected}"] if command else [])
    assert render.parts(repo.root) == render.parts(repo.root)


@pytest.mark.parametrize(
    ("manifests", "install_lines"),
    [
        (("pyproject.toml",), ()),
        (("package.json", "package-lock.json"), ("npm ci --no-audit --no-fund",)),
        (("package.json", "package-lock.json", "pyproject.toml"), ("npm ci --no-audit --no-fund",)),
    ],
    ids=["python-only", "node-tooling", "python-and-node-tooling"],
)
def test_tools_installs_each_stacks_dependencies_after_mise(repo: Repo, manifests: tuple[str, ...], install_lines: tuple[str, ...]) -> None:
    for manifest in manifests:
        repo.write(manifest, '{"scripts": {"build": "vite build"}}' if manifest == "package.json" else '[project]\nname = "x"\n')
    base = render.parts(repo.root)[".blueprint/base.just"]
    tools = base.split("\ntools:\n", 1)[1].split("\n\n", 1)[0]
    assert tools.splitlines() == [
        "    mise trust --yes .",
        '    MISE_IGNORED_CONFIG_PATHS="$HOME/.config/mise" mise install --locked',
        *(f"    {line}" for line in install_lines),
    ]


@pytest.mark.parametrize("stacks", [("node",), ("node", "node-tooling"), ("node-tooling", "node")])
def test_node_install_is_rendered_once_for_either_node_stack(repo: Repo, monkeypatch: pytest.MonkeyPatch, stacks: tuple[str, ...]) -> None:
    repo.write("package.json", "{}")
    repo.write("package-lock.json", "{}")
    monkeypatch.setattr(render, "detect_stacks", lambda _repo: stacks)
    base = render.parts(repo.root)[".blueprint/base.just"]
    assert base.count("    npm ci --no-audit --no-fund\n") == 1


def test_write_creates_the_parts_and_a_justfile_importing_them(repo: Repo) -> None:
    _python_and_shell(repo)
    render.write(repo.root)
    text = (repo.root / "justfile").read_text()
    for name in render.parts(repo.root):
        if name.endswith(".just"):
            assert f"import '{name}'" in text
    assert "set allow-duplicate-recipes" in text
    assert render.check(repo.root) == 0


def test_write_keeps_the_repos_own_recipes_and_adds_only_the_missing_imports(repo: Repo) -> None:
    _python(repo)
    repo.write("justfile", "check-extra:\n    echo mine\n")
    render.write(repo.root)
    text = (repo.root / "justfile").read_text()
    assert "check-extra:\n    echo mine\n" in text
    assert text.count("import '.blueprint/base.just'") == 1
    render.write(repo.root)
    assert (repo.root / "justfile").read_text() == text


@needs_just
def test_the_two_stack_gate_resolves_in_just(repo: Repo) -> None:
    _python_and_shell(repo)
    render.write(repo.root)
    result = _just(repo, "--dry-run", "check")
    assert result.returncode == 0, result.stderr


@needs_just
def test_a_recipe_the_repo_defines_wins_over_the_base_one(repo: Repo) -> None:
    _python(repo)
    render.write(repo.root)
    with (repo.root / "justfile").open("a") as fh:
        fh.write("\nlint:\n    echo repo-lint\n")
    shown = _just(repo, "--show", "lint")
    assert shown.returncode == 0, shown.stderr
    assert "repo-lint" in shown.stdout
    assert render.check(repo.root) == 0, "an override in the repo's justfile is not drift of the base"


def test_a_hand_edited_base_is_drift_and_names_the_file(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _python(repo)
    render.write(repo.root)
    base = repo.root / ".blueprint" / "base.just"
    base.write_text(base.read_text() + "\nsneaky:\n    true\n")
    assert render.check(repo.root) == 1
    assert ".blueprint/base.just" in capsys.readouterr().err


def test_a_missing_part_is_drift(repo: Repo) -> None:
    _python(repo)
    render.write(repo.root)
    (repo.root / ".blueprint" / "python.just").unlink()
    assert render.check(repo.root) == 1


def test_a_part_of_a_stack_the_repo_no_longer_has_is_drift(repo: Repo) -> None:
    _python(repo)
    render.write(repo.root)
    (repo.root / ".blueprint" / "shell.just").write_text("scripts:\n    true\n")
    assert render.check(repo.root) == 1


def test_a_justfile_that_does_not_import_a_part_is_drift(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _python(repo)
    render.write(repo.root)
    (repo.root / "justfile").write_text("check:\n    true\n")
    assert render.check(repo.root) == 1
    assert "import '.blueprint/base.just'" in capsys.readouterr().err


def test_a_repo_that_never_rendered_fails_the_check_not_passes(repo: Repo) -> None:
    _python(repo)
    assert render.check(repo.root) == 1


def test_the_cli_writes_then_checks(repo: Repo, tmp_path: Path) -> None:
    _python(repo)
    assert main(["gate", "render", "--repo", str(repo.root), "--check"]) == 1
    assert main(["gate", "render", "--repo", str(repo.root)]) == 0
    assert main(["gate", "render", "--repo", str(repo.root), "--check"]) == 0


def test_the_release_gate_runs_the_whole_form_of_each_step_and_a_floor(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "x"\n[tool.blueprint.gate]\nrelease-gate = true\n')
    repo.write("uv.lock", "")
    parts = render.parts(repo.root)
    assert '"secrets-all"' in parts[".blueprint/base.just"]
    assert '"test-all"' in parts[".blueprint/base.just"]
    assert "blueprint gate test-all" in parts[".blueprint/python.just"]
    assert "\ntest-all *args:" in parts[".blueprint/python.just"]


def test_release_recipes_are_absent_by_default(repo: Repo) -> None:
    _python(repo)
    text = "\n".join(render.parts(repo.root).values())
    for name in ("check-all", "steps-all", "test-all", "secrets-all"):
        assert f"\n{name}:" not in text
        assert f"\n{name} +" not in text
    assert "\ncheck-extra:" in text


def test_the_linters_over_the_whole_repo_are_always_rendered(repo: Repo) -> None:
    # They are seconds, not a full run: a repo's static gate (`lint`, `spell`) never needs release-gate.
    _python(repo)
    text = "\n".join(render.parts(repo.root).values())
    assert "\nlint:" in text
    assert "\nspell:" in text


@pytest.mark.parametrize("step", ["test-all", "steps-all"])
def test_a_whole_recipe_referenced_by_the_repo_stays_without_release_gate(repo: Repo, step: str) -> None:
    _python(repo)
    repo.write("justfile", f"check-extra: {step}\n")
    text = "\n".join(render.parts(repo.root).values())
    assert f"\n{step}:" in text or f"\n{step} +" in text or f"\n{step} *args:" in text
    assert "\ncheck-all:" not in text


def test_the_defaults_cover_exactly_the_steps_this_gate_runs(repo: Repo) -> None:
    _python(repo)
    table = tomllib.loads(render.parts(repo.root)[render.INPUTS_PART])
    assert {k for k, v in table.items() if isinstance(v, list)} == {"blueprint", "secrets", "lint-changed", "typecheck", "deps", "test"}
    assert "*.py" in table["typecheck"]


def test_a_shell_stack_adds_the_scripts_default(repo: Repo) -> None:
    _python_and_shell(repo)
    table = tomllib.loads(render.parts(repo.root)[render.INPUTS_PART])
    assert table["scripts"] == ["*.sh", "*.shellcheckrc"]


def test_every_wide_default_says_why_in_a_known_kind(repo: Repo) -> None:
    _python(repo)
    table = tomllib.loads(render.parts(repo.root)[render.INPUTS_PART])
    wide = [s for s, v in table.items() if isinstance(v, list) and "*" in v]
    assert sorted(wide) == sorted(table["wide"])
    assert all(reason.split(":")[0] in gate_inputs.WIDE_KINDS for reason in table["wide"].values())


def test_an_extra_step_named_like_a_default_gets_that_default(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "x"\n[tool.blueprint.gate]\nsteps = ["arch"]\n')
    repo.write("uv.lock", "")
    table = tomllib.loads(render.parts(repo.root)[render.INPUTS_PART])
    assert "*.py" in table["arch"]


_IMPORTLINTER = '[project]\nname = "x"\n[tool.importlinter]\nroot_package = "x"\n'


def test_a_python_repo_with_import_linter_contracts_renders_the_arch_step(repo: Repo) -> None:
    repo.write("pyproject.toml", _IMPORTLINTER)
    repo.write("uv.lock", "")
    parts = render.parts(repo.root)
    assert "\narch:\n    uv run lint-imports --cache-dir {{ justfile_directory() }}/.cache/import_linter" in parts[".blueprint/python.just"]
    assert 'export HYPOTHESIS_STORAGE_DIRECTORY := justfile_directory() / ".cache/hypothesis"' in parts[".blueprint/python.just"]
    assert '"arch"' in parts[".blueprint/base.just"]
    assert "*.py" in tomllib.loads(parts[render.INPUTS_PART])["arch"]


def test_a_python_repo_without_contracts_renders_no_arch_step(repo: Repo) -> None:
    _python(repo)
    parts = render.parts(repo.root)
    assert "arch:" not in parts[".blueprint/python.just"]
    assert '"arch"' not in parts[".blueprint/base.just"]


def test_an_importlinter_file_also_counts_as_contracts(repo: Repo) -> None:
    _python(repo)
    repo.write(".importlinter", "[importlinter]\nroot_package = x\n")
    assert "\narch:" in render.parts(repo.root)[".blueprint/python.just"]


def test_a_step_named_twice_is_run_once(repo: Repo) -> None:
    repo.write("pyproject.toml", _IMPORTLINTER + '[tool.blueprint.gate]\nsteps = ["arch"]\n')
    repo.write("uv.lock", "")
    assert render.parts(repo.root)[".blueprint/base.just"].count('"arch"') == 1
