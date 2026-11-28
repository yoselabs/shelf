"""Stack roots (ADR 0034): a stack is found at the repo root or one folder down, judged with its own profile, and rendered to run there."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from blueprint.runner import run

if TYPE_CHECKING:
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


# --- rendering: each stack's steps run in its folder, and read only it ---------------------------------------------------------


def _both(repo: Repo) -> None:
    _python(repo, "backend/")
    repo.write("frontend/package.json", json.dumps({"name": "web", "scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "1"}}))
    repo.write("frontend/package-lock.json", "{}")
    repo.write("frontend/biome.json", "{}")


def test_the_backend_recipes_run_in_the_backend_folder(repo: Repo) -> None:
    from blueprint import render  # noqa: PLC0415 -- the engine imports every check

    _both(repo)
    parts = render.parts(repo.root)
    python = parts[".blueprint/python.just"]
    assert "[working-directory('backend')]" in python
    assert "@PY@" not in python
    assert python.count("[working-directory('backend')]") == 10  # every recipe but `deps-all` (no body) and `test-all` (release gate)
    assert "cd frontend &&" in parts[".blueprint/node.just"]
    base = parts[".blueprint/base.just"]
    assert "uv run --project backend python -m any_gate steps" in base
    assert "uv run --project backend blueprint gate blueprint --repo ." in base
    assert "uv run python" not in base


def test_a_stack_at_the_root_renders_what_it_always_did(repo: Repo) -> None:
    from blueprint import render  # noqa: PLC0415 -- the engine imports every check

    _python(repo)
    parts = render.parts(repo.root)
    assert "working-directory" not in "".join(parts.values())
    assert "--project" not in "".join(parts.values())
    assert "@PY@" not in "".join(parts.values())


def test_just_resolves_a_working_directory_from_the_root_justfile_through_an_import(repo: Repo) -> None:
    just = Path(sys.executable).parent / "just"
    if not just.is_file():
        pytest.skip("rust-just is not installed beside this interpreter")
    repo.write("backend/marker.txt", "x")
    repo.write(".blueprint/part.just", "[working-directory('backend')]\nwhere:\n    @pwd\n")
    repo.write("justfile", "import '.blueprint/part.just'\n")
    done = subprocess.run([str(just), "where"], cwd=repo.root, capture_output=True, text=True, check=False, timeout=60)
    assert done.stdout.strip().endswith("/backend"), done.stderr


def test_a_frontend_edit_starts_no_python_step_and_a_backend_edit_starts_no_node_step(repo: Repo, tmp_path: Path) -> None:
    from blueprint import render  # noqa: PLC0415 -- the engine imports every check

    inputs = pytest.importorskip("any_gate.inputs")
    _both(repo)
    repo.write("justfile", "check:\n\t@:\n")
    for name, text in render.parts(repo.root).items():
        repo.write(name, text)
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True, timeout=60)
    repo.git("add", "-A")
    repo.git("commit", "-qm", "base")
    repo.git("remote", "add", "origin", str(remote))
    repo.git("push", "-q", "-u", "origin", "main")
    python_steps = {"typecheck", "deps", "test"}
    node_steps = {"ui-lint", "ui-test"}
    names = sorted(python_steps | node_steps)
    repo.write("frontend/app.js", "export const x = 1\n")
    skips, runs = inputs.explain(repo.root, names, recorded=lambda: True)
    assert python_steps <= set(skips), (skips, runs)
    assert node_steps <= set(runs)
    repo.git("add", "-A")
    repo.git("commit", "-qm", "frontend")
    repo.git("push", "-q")
    repo.write("backend/src/app/x.py", "x = 1\n")
    skips, runs = inputs.explain(repo.root, names, recorded=lambda: True)
    assert node_steps <= set(skips), (skips, runs)
    assert python_steps <= set(runs)


# --- the repo-level checks that read the Python stack's files --------------------------------------------------------------------


def test_the_lint_selection_asked_from_backend_sees_both_tracked_and_untracked_changes(repo: Repo, tmp_path: Path) -> None:
    from blueprint import gate_py  # noqa: PLC0415 -- the engine imports every check

    pytest.importorskip("any_gate")
    _python(repo, "backend/")
    repo.write("backend/src/app/old.py", "x = 1\n")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True, timeout=60)
    repo.git("add", "-A")
    repo.git("commit", "-qm", "base")
    repo.git("remote", "add", "origin", str(remote))
    repo.git("push", "-q", "-u", "origin", "main")
    repo.write("backend/src/app/old.py", "x = 2\n")
    repo.write("backend/src/app/new.py", "y = 1\n")
    repo.write("frontend/app.py", "z = 1\n")
    found = gate_py.changed(repo.root / "backend", ["*.py"], gate_py.LINT_CONFIGS, scope="changed")
    assert found is not None
    assert sorted(found) == ["src/app/new.py", "src/app/old.py"]


def test_the_local_shelf_source_guard_reads_the_backend_pyproject(repo: Repo, monkeypatch: pytest.MonkeyPatch) -> None:
    from blueprint import guard  # noqa: PLC0415 -- the engine imports every check

    repo.write(
        "backend/pyproject.toml", _PYPROJECT + '[tool.uv.sources]\nanyllm = { path = "../shelf/packages/anyllm", editable = true }\n'
    )
    repo.git("add", "-A")
    repo.git("commit", "-qm", "local source")
    monkeypatch.chdir(repo.root)
    assert guard.check(committed=True) == 1


def test_the_preset_check_finds_the_backend_pyproject_instead_of_refusing_to_verify(repo: Repo) -> None:
    from blueprint import preset  # noqa: PLC0415 -- the engine imports every check

    _python(repo, "backend/")
    assert preset.check(repo.root) in {0, 1}  # 2 is "cannot verify, not a pass"
