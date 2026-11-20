"""`blueprint gate render`: the justfile parts the blueprint owns, written per detected stack, and the drift check on them.

The repo's own `justfile` imports `.blueprint/*.just` and fills the named extension points; a recipe it defines itself wins over
the base one (`set allow-duplicate-recipes`, chosen over `mod` in ADR 0029).
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest
from blueprint import render
from blueprint.__main__ import main

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
    assert sorted(parts) == [".blueprint/base.just", ".blueprint/python.just"]
    assert '"lint" "typecheck"' in parts[".blueprint/base.just"]
    assert "\ntypecheck:" in parts[".blueprint/python.just"]


def test_two_stacks_render_two_parts_and_the_check_names_both_steps(repo: Repo) -> None:
    _python_and_shell(repo)
    parts = render.parts(repo.root)
    assert sorted(parts) == [".blueprint/base.just", ".blueprint/python.just", ".blueprint/shell.just"]
    assert '"scripts"' in parts[".blueprint/base.just"]


def test_every_repo_gets_the_secret_scan_step_and_its_recipes(repo: Repo) -> None:
    base = render.parts(repo.root)[".blueprint/base.just"]
    assert '"blueprint" "secrets"' in base
    assert "\nsecrets:\n    uv run python -m blueprint.secret_scan range" in base
    assert "\nsecrets-all:\n    uv run python -m blueprint.secret_scan full" in base


def test_a_repo_with_no_known_stack_gets_only_the_base(repo: Repo) -> None:
    assert sorted(render.parts(repo.root)) == [".blueprint/base.just"]


def test_rendering_is_deterministic(repo: Repo) -> None:
    _python_and_shell(repo)
    assert render.parts(repo.root) == render.parts(repo.root)


def test_write_creates_the_parts_and_a_justfile_importing_them(repo: Repo) -> None:
    _python_and_shell(repo)
    render.write(repo.root)
    text = (repo.root / "justfile").read_text()
    for name in render.parts(repo.root):
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
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    repo.write("uv.lock", "")
    parts = render.parts(repo.root)
    assert '"secrets-all"' in parts[".blueprint/base.just"]
    assert '"test-all"' in parts[".blueprint/base.just"]
    assert "--cov-fail-under" in parts[".blueprint/python.just"]
    assert "\ntest-all:" in parts[".blueprint/python.just"]
