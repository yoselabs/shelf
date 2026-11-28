"""`blueprint gate render` for images: one `images` step when a Dockerfile or compose file is tracked, each tool for the files present.

The recipe is what a2kay wrote by hand (hadolint, dockerfmt, docker build --check, dclint, yamlfmt, compose config). The digest-pin check
is optional: `[tool.blueprint.gate] image-pins = true` adds it, run as
`python -m blueprint.recipes.check_dockerfile_pins` so a repo copies nothing.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tomllib
from typing import TYPE_CHECKING

import pytest
from blueprint import render
from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from pathlib import Path

    from blueprint.testing import Repo

PINNED = "FROM python:3.12-slim@sha256:" + "a" * 64 + "\n"
UNPINNED = "FROM python:3.12-slim\n"
COMPOSE = "services:\n  db:\n    image: postgres:17\n"


def _steps(repo: Repo) -> list[str]:
    base = render.parts(repo.root)[".blueprint/base.just"]
    line = next(line for line in base.splitlines() if line.startswith("check:"))
    return re.findall(r'"([\w-]+)"', line.split("(steps ", 1)[1].split(")", 1)[0])


def _images(repo: Repo) -> str:
    return render.parts(repo.root)[".blueprint/images.just"]


def test_a_repo_with_no_image_files_renders_no_images_step(repo: Repo) -> None:
    repo.write("README.md", "x\n")
    repo.commit()
    assert ".blueprint/images.just" not in render.parts(repo.root)
    assert "images" not in _steps(repo)


def test_a_dockerfile_renders_the_dockerfile_tools_only(repo: Repo) -> None:
    repo.write("Dockerfile", PINNED)
    repo.commit()
    images = _images(repo)
    assert "images" in _steps(repo)
    for tool in ("hadolint", "dockerfmt --check -n", "docker build --check"):
        assert tool in images
    assert "dclint" not in images
    assert "yamlfmt" not in images


def test_a_compose_file_renders_the_compose_tools_only(repo: Repo) -> None:
    repo.write("compose.yml", COMPOSE)
    repo.commit()
    images = _images(repo)
    for tool in ("dclint --max-warnings 0", "yamlfmt -lint", "config --no-interpolate -q"):
        assert tool in images
    assert "hadolint" not in images
    assert "dockerfmt" not in images


def test_both_kinds_render_every_tool_and_name_only_what_is_present(repo: Repo) -> None:
    repo.write("Dockerfile", PINNED)
    repo.write("deploy/compose.yaml", COMPOSE)
    repo.commit()
    images = _images(repo)
    assert all(t in images for t in ("hadolint", "dockerfmt", "dclint", "yamlfmt", "docker build --check", "config --no-interpolate -q"))
    assert "for t in hadolint dockerfmt docker dclint yamlfmt" in images  # a missing tool is said by name, exit 2


def test_the_digest_pin_check_is_off_by_default_and_never_copied(repo: Repo) -> None:
    repo.write("Dockerfile", UNPINNED)
    repo.commit()
    assert "check_dockerfile_pins" not in _images(repo)


def test_image_pins_true_runs_the_check_through_the_package_entry_point(repo: Repo) -> None:
    repo.write("Dockerfile", PINNED)
    repo.write("pyproject.toml", '[project]\nname = "x"\n[tool.blueprint.gate]\nimage-pins = true\nimage-pin-contexts = ["shelf"]\n')
    repo.commit()
    assert "uv run python -I -m blueprint.recipes.check_dockerfile_pins --context shelf" in _images(repo)


def test_the_images_defaults_name_the_image_files_and_their_configs(repo: Repo) -> None:
    repo.write("Dockerfile", PINNED)
    repo.commit()
    globs = tomllib.loads(render.parts(repo.root)[render.INPUTS_PART])["images"]
    for glob in ("*Dockerfile*", "*compose*", "*.hadolint.yaml", "*.dclintrc*", "*.yamlfmt*", "mise.*"):
        assert glob in globs


def test_the_pins_row_is_not_required(repo: Repo) -> None:
    repo.write("Dockerfile", UNPINNED)
    repo.commit()
    rows = {r.id: r.verdict for r in run(repo.root, concern="stack", env=repo.env).rows}
    assert rows["stack.dockerfile.dependencies"] is Verdict.NOT_APPLICABLE


def test_the_pins_row_passes_when_the_rendered_images_recipe_runs_the_check(repo: Repo) -> None:
    repo.write("Dockerfile", PINNED)
    repo.write("pyproject.toml", '[project]\nname = "x"\n[tool.blueprint.gate]\nimage-pins = true\n')
    repo.commit()
    render.write(repo.root)
    repo.commit()
    rows = {r.id: r.verdict for r in run(repo.root, concern="stack", env=repo.env).rows}
    assert rows["stack.dockerfile.dependencies"] is Verdict.PASSING


def test_the_compose_dependencies_row_passes_when_the_rendered_images_recipe_runs_compose_pins(repo: Repo) -> None:
    # shelf-0lv1: a2kay on 0.17.0 got "not set up" for a gate that pins images by the rendered step.
    repo.write("compose.yml", "services:\n  db:\n    image: postgres:17@sha256:" + "a" * 64 + "\n")
    repo.write("pyproject.toml", '[project]\nname = "x"\n[tool.blueprint.gate]\nimage-pins = true\n')
    repo.commit()
    render.write(repo.root)
    repo.commit()
    rows = {r.id: r.verdict for r in run(repo.root, concern="stack", env=repo.env).rows}
    assert rows["stack.compose.dependencies"] is Verdict.PASSING


def test_the_compose_dependencies_row_still_wants_a_pin_check_without_image_pins(repo: Repo) -> None:
    repo.write("compose.yml", COMPOSE)
    repo.commit()
    render.write(repo.root)
    repo.commit()
    rows = {r.id: r.verdict for r in run(repo.root, concern="stack", env=repo.env).rows}
    assert rows["stack.compose.dependencies"] is Verdict.NOT_SET_UP


def _module(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-m", "blueprint.recipes.check_dockerfile_pins", *args], cwd=cwd, capture_output=True, text=True, check=False
    )


def test_the_entry_point_fails_an_unpinned_image_and_passes_a_pinned_one(tmp_path: Path) -> None:
    (tmp_path / "a.Dockerfile").write_text(UNPINNED)
    (tmp_path / "b.Dockerfile").write_text(PINNED)
    bad = _module("a.Dockerfile", cwd=tmp_path)
    assert bad.returncode == 1
    assert "a.Dockerfile:1" in bad.stdout
    assert _module("b.Dockerfile", cwd=tmp_path).returncode == 0


@pytest.mark.skipif(shutil.which("just") is None, reason="just is not installed")
def test_the_rendered_images_part_is_valid_just(repo: Repo) -> None:
    repo.write("Dockerfile", PINNED)
    repo.write("compose.yml", COMPOSE)
    repo.commit()
    render.write(repo.root)
    done = subprocess.run(["just", "--list"], cwd=repo.root, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    assert "images" in done.stdout
    assert render.check(repo.root) == 0


def test_the_image_stack_rows_accept_what_the_render_wrote(repo: Repo) -> None:
    repo.write("Dockerfile", PINNED)
    repo.write("compose.yml", COMPOSE)
    for name, text in {".hadolint.yaml": "ignored: []\n", ".yamlfmt.yaml": "formatter: {}\n", ".dclintrc": "{}\n"}.items():
        repo.write(name, text)
    repo.commit()
    render.write(repo.root)
    repo.commit()
    rows = {r.id: r.verdict for r in run(repo.root, concern="stack", env=repo.env).rows}
    for row in ("dockerfile.formatter", "dockerfile.linter", "dockerfile.tests", "compose.formatter", "compose.linter", "compose.types"):
        assert rows[f"stack.{row}"] is Verdict.PASSING, row


def test_the_pins_row_fails_when_the_check_is_named_but_the_gate_never_runs_it(repo: Repo) -> None:
    repo.write("Dockerfile", PINNED)
    repo.write("justfile", "check: lint\nlint:\n    true\nunused:\n    python -m blueprint.recipes.check_dockerfile_pins\n")
    repo.commit()
    rows = {r.id: r.verdict for r in run(repo.root, concern="stack", env=repo.env).rows}
    assert rows["stack.dockerfile.dependencies"] is Verdict.FAILING


def _pin_repo(repo: Repo, *, exempt: str = "") -> None:
    repo.write("pyproject.toml", f'[project]\nname = "x"\n[tool.blueprint.gate]\nimage-pins = true\n{exempt}')
    repo.commit()


def test_image_pins_true_renders_one_compose_pin_pass_with_the_exemptions(repo: Repo) -> None:
    repo.write("compose.yml", COMPOSE)
    _pin_repo(repo, exempt='image-pin-exempt = ["ghcr.io/org/app:${IMAGE_TAG:?"]\n')
    images = _images(repo)
    assert images.count("blueprint.compose_pins") == 1
    assert "--exempt 'ghcr.io/org/app:${IMAGE_TAG:?'" in images


def test_the_compose_pin_pass_is_off_without_image_pins(repo: Repo) -> None:
    repo.write("compose.yml", COMPOSE)
    repo.commit()
    assert "compose_pins" not in _images(repo)


def _pins(tmp_path: Path, text: str, *flags: str) -> tuple[int, str]:
    path = tmp_path / "compose.yml"
    path.write_text(text)
    done = subprocess.run(
        [sys.executable, "-I", "-m", "blueprint.compose_pins", *flags, str(path)], capture_output=True, text=True, check=False
    )
    return done.returncode, done.stdout


def test_the_compose_pin_pass_fails_an_undigested_image_and_names_it(tmp_path: Path) -> None:
    code, out = _pins(tmp_path, COMPOSE)
    assert code == 1
    assert "compose.yml:3 'postgres:17' has no @sha256" in out


def test_the_compose_pin_pass_accepts_digests_quoted_listed_and_commented(tmp_path: Path) -> None:
    pinned = "postgres:17@sha256:" + "a" * 64
    text = f'services:\n  db:\n    image: {pinned} # why\n  web:\n    image: "{pinned}"\n# image: ignored:1\n'
    assert _pins(tmp_path, text)[0] == 0


def test_the_compose_pin_pass_honours_the_exemption_by_prefix_only(tmp_path: Path) -> None:
    own = "services:\n  app:\n    image: ghcr.io/org/app:${IMAGE_TAG:?set}\n  db:\n    image: postgres:17\n"
    code, out = _pins(tmp_path, own, "--exempt", "ghcr.io/org/app:${IMAGE_TAG:?")
    assert code == 1
    assert "app" not in out
    assert "postgres:17" in out


def test_a_digest_must_be_64_hex_at_the_end(tmp_path: Path) -> None:
    assert _pins(tmp_path, "services:\n  a:\n    image: x:1@sha256:abc\n")[0] == 1
