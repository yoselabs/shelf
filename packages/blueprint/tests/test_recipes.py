"""Recipes: files `blueprint recipe <name>` prints for a repo to copy and own (ADR 0004)."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from blueprint.__main__ import RECIPE_FILES, RECIPES, main

if TYPE_CHECKING:
    import pytest
    from blueprint.testing import Repo

_GUID = "0123456789abcdef0123456789abcdef"


def test_every_recipe_prints_its_file(capsys: pytest.CaptureFixture[str]) -> None:
    for name, file in RECIPE_FILES.items():
        assert main(["recipe", name]) == 0
        assert capsys.readouterr().out == (RECIPES / file).read_text()


def _run(recipe: str, args: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    # Loaded from its file, the way a repo runs its copy; in-process, so coverage sees it.
    spec = importlib.util.spec_from_file_location(recipe.replace("-", "_"), RECIPES / RECIPE_FILES[recipe])
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    code = module.main(args)
    return code, capsys.readouterr().out


def _integrity(repo: Repo, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    return _run("unity-integrity", [str(repo.root)], capsys)


def _clean_unity(repo: Repo) -> None:
    repo.write("ProjectSettings/EditorSettings.asset", "  m_SerializationMode: 2\n")
    repo.write("ProjectSettings/VersionControlSettings.asset", "  m_Mode: Visible Meta Files\n")
    repo.write("Assets/Player.cs", "class Player {}\n")
    repo.write("Assets/Player.cs.meta", f"guid: {_GUID}\n")


def test_the_unity_integrity_script_passes_a_clean_project(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _clean_unity(repo)
    assert _integrity(repo, capsys) == (0, "")


def test_the_unity_integrity_script_fails_on_each_broken_rule(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _clean_unity(repo)
    repo.write("Assets/Enemy.cs", "class Enemy {}\n")
    repo.write("Assets/Gone.cs.meta", f"guid: {_GUID}\n")
    repo.write("ProjectSettings/EditorSettings.asset", "  m_SerializationMode: 0\n")
    code, out = _integrity(repo, capsys)
    assert code == 1
    for needle in ("asset without .meta: Assets/Enemy.cs", "orphan meta", "duplicate guid", "Force Text"):
        assert needle in out, needle


def _coverage(repo: Repo, line: float, branch: float, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    summary = repo.write("cov/Summary.json", f'{{"summary": {{"linecoverage": {line}, "branchcoverage": {branch}}}}}')
    floor = repo.write("coverage-floor.json", '{"line": 89.0, "branch": 75.0}')
    return _run("dotnet-coverage", [str(summary), str(floor)], capsys)


def test_the_coverage_floor_passes_at_or_over_the_floor(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = _coverage(repo, 89.9, 75.0, capsys)
    assert code == 0
    assert "line 89.9% (floor 89.0%)" in out


def test_the_coverage_floor_fails_under_it_and_names_the_metric(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = _coverage(repo, 91.0, 74.2, capsys)
    assert code == 1
    assert "branch coverage 74.2% < floor 75.0%" in out
    assert "line coverage" not in out.split("below floor")[-1]


_UID = "uid://b1"


def _godot_project(repo: Repo) -> None:
    repo.write("project.godot", 'config/features=PackedStringArray("4.7", "C#")\n')
    repo.write("Game.csproj", '<Project Sdk="Godot.NET.Sdk/4.7.2"></Project>\n')
    repo.write("Panel.cs", "partial class Panel {}\n")
    repo.write("Panel.cs.uid", f"{_UID}\n")
    repo.write(
        "Main.tscn",
        '[gd_scene load_steps=2 format=3 uid="uid://m1"]\n\n'
        f'[ext_resource type="Script" uid="{_UID}" path="res://Panel.cs" id="1_a"]\n\n'
        '[node name="Main" type="Control"]\nscript = ExtResource("1_a")\n',
    )


def test_the_godot_check_passes_a_clean_project(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _godot_project(repo)
    assert _run("godot-integrity", [str(repo.root)], capsys) == (0, "godot surface: clean\n")


def test_the_godot_check_fails_where_the_import_log_stays_quiet(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _godot_project(repo)
    (repo.root / "Panel.cs.uid").unlink()
    repo.write("Other.tscn", '[gd_scene format=3]\n\n[ext_resource type="Script" path="res://Gone.cs" id="1_b"]\ngarbage here\n')
    repo.write("Game.csproj", '<Project Sdk="Godot.NET.Sdk/4.6.1"></Project>\n')
    code, out = _run("godot-integrity", [str(repo.root)], capsys)
    assert code == 1
    for needle in ("Panel.cs has no committed .uid", "does not exist", "not a section", "never used", "says Godot.NET.Sdk 4.6"):
        assert needle in out, needle


_DIGEST = "@sha256:" + "a" * 64


def _pins(repo: Repo, text: str, capsys: pytest.CaptureFixture[str], *extra: str) -> tuple[int, str]:
    path = repo.write("Dockerfile", text)
    return _run("dockerfile-pins", [*extra, str(path)], capsys)


def test_digest_pinned_images_pass(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    text = (
        f"ARG PY=3.12\nFROM --platform=linux/amd64 python:${{PY}}-slim{_DIGEST} AS base\n"
        f"COPY --from=ghcr.io/astral-sh/uv:0.13.0{_DIGEST} /uv /bin/\nFROM base\nCOPY --from=base /x /y\nFROM scratch\n"
    )
    assert _pins(repo, text, capsys)[0] == 0


def test_a_tag_without_a_digest_fails_and_names_the_line(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = _pins(repo, "FROM python:3.12-slim\nCOPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/\n", capsys)
    assert code == 1
    assert ":1 'python:3.12-slim'" in out
    assert ":2 'ghcr.io/astral-sh/uv:latest'" in out


def test_a_build_context_is_not_an_image(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    text = f"FROM python:3.12-slim{_DIGEST}\nCOPY --from=shelf pyproject.toml /shelf/\n"
    assert _pins(repo, text, capsys)[0] == 0


def test_an_image_from_an_unset_arg_cannot_be_judged_and_fails(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = _pins(repo, "FROM python:${PYTHON_VERSION}-slim\n", capsys)
    assert code == 1
    assert "PYTHON_VERSION" in out


_CLEAN_COMPOSE = """services:
  web:
    image: nginx:1.27@sha256:{d}
    ports: ["127.0.0.1:8080:80"]
    networks: [front]
    healthcheck: {{test: ["CMD", "true"]}}
networks:
  front: {{}}
""".format(d="a" * 64)


def _conftest(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    # Pinned in the shelf's mise.toml; a missing conftest is a failure, never a skipped test.
    assert shutil.which("conftest"), "conftest is not installed: run `just tools`"
    return subprocess.run(["conftest", *args], cwd=cwd, capture_output=True, text=True, check=False)


def _policy(repo: Repo) -> None:
    repo.write("policy/compose.rego", (RECIPES / RECIPE_FILES["compose-policy"]).read_text())


def test_the_compose_policy_passes_its_own_unit_tests(repo: Repo) -> None:
    _policy(repo)
    repo.write("policy/compose_test.rego", (Path(__file__).parent / "fixtures/compose_policy_test.rego").read_text())
    result = _conftest("verify", "--policy", "policy", cwd=repo.root)
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_clean_compose_file_passes_the_policy(repo: Repo) -> None:
    _policy(repo)
    repo.write("compose.yml", _CLEAN_COMPOSE)
    result = _conftest("test", "--combine", "--policy", "policy", "compose.yml", cwd=repo.root)
    assert result.returncode == 0, result.stdout


_BAD_COMPOSE = _CLEAN_COMPOSE.replace('    ports: ["127.0.0.1:8080:80"]\n', '    ports: ["8080:80"]\n    privileged: true\n').replace(
    '    healthcheck: {test: ["CMD", "true"]}\n', "    volumes: [/var/run/docker.sock:/var/run/docker.sock]\n"
)
_OVERRIDES = "docs/blueprint/blueprint.toml"


def _override_toml(rule: str, service: str, reason: str = "the exporter reads host counters") -> str:
    return f'[[override]]\nid = "compose.{rule}"\nscope = "service:{service}"\nreason = "{reason}"\nexpires = 2099-01-01\n'


def _test_with_data(repo: Repo) -> subprocess.CompletedProcess[str]:
    return _conftest("test", "--combine", "--policy", "policy", _OVERRIDES, "compose.yml", cwd=repo.root)


def test_each_rule_is_denied_unless_an_override_excuses_it_with_a_reason(repo: Repo) -> None:
    _policy(repo)
    repo.write("compose.yml", _BAD_COMPOSE)
    repo.write(_OVERRIDES, "[settings]\nx = 1\n")
    out = _test_with_data(repo)
    assert out.returncode == 1
    for rule in ("privileged", "docker socket", "every interface", "no healthcheck"):
        assert rule in out.stdout, rule
    repo.write(_OVERRIDES, _override_toml("privileged", "web"))
    assert "privileged" not in _test_with_data(repo).stdout


def test_an_override_for_another_service_or_rule_excuses_nothing(repo: Repo) -> None:
    _policy(repo)
    repo.write("compose.yml", _BAD_COMPOSE)
    repo.write(_OVERRIDES, _override_toml("privileged", "db") + _override_toml("host_network", "web"))
    assert "privileged" in _test_with_data(repo).stdout


def test_an_override_with_a_blank_reason_excuses_nothing(repo: Repo) -> None:
    _policy(repo)
    repo.write("compose.yml", _BAD_COMPOSE)
    repo.write(_OVERRIDES, _override_toml("privileged", "web", reason=" "))
    assert "privileged" in _test_with_data(repo).stdout


def test_an_expired_override_excuses_nothing(repo: Repo) -> None:
    _policy(repo)
    repo.write("compose.yml", _BAD_COMPOSE)
    repo.write(_OVERRIDES, _override_toml("privileged", "web").replace("2099-01-01", "2020-01-01"))
    assert "privileged" in _test_with_data(repo).stdout


def test_x_policy_exempt_still_excuses_and_warns_with_the_move(repo: Repo) -> None:
    _policy(repo)
    repo.write(
        "compose.yml",
        _CLEAN_COMPOSE.replace(
            "    networks: [front]\n", '    networks: [front]\n    privileged: true\n    x-policy-exempt: {privileged: "why"}\n'
        ),
    )
    repo.write(_OVERRIDES, "[settings]\nx = 1\n")
    out = _test_with_data(repo)
    assert out.returncode == 0, out.stdout
    assert "x-policy-exempt" in out.stdout
    assert 'id = "compose.privileged"' in out.stdout
    assert 'scope = "service:web"' in out.stdout


def test_the_old_command_line_warns_and_still_judges(repo: Repo) -> None:
    _policy(repo)
    repo.write("compose.yml", _CLEAN_COMPOSE)
    clean = _conftest("test", "--policy", "policy", "compose.yml", cwd=repo.root)
    assert clean.returncode == 0
    assert "--combine" in clean.stdout
    repo.write("compose.yml", _BAD_COMPOSE)
    assert _conftest("test", "--policy", "policy", "compose.yml", cwd=repo.root).returncode == 1


def test_the_old_command_line_still_reads_a_top_level_exempt_block(repo: Repo) -> None:
    _policy(repo)
    bad = (
        _CLEAN_COMPOSE.replace('    ports: ["127.0.0.1:8080:80"]\n', "    privileged: true\n")
        + 'x-policy-exempt: {web: {privileged: "why"}}\n'
    )
    repo.write("compose.yml", bad)
    out = _conftest("test", "--policy", "policy", "compose.yml", cwd=repo.root)
    assert out.returncode == 0, out.stdout
    assert "compose.privileged" in out.stdout


# a2kay's owner, 2026-10-12: a hook that cannot fail tells nothing. `bd dolt push` failed over HTTPS on an SSH-only box and
# the pre-push hook still printed Passed.
def _dolt_push_entry() -> str:
    text = (RECIPES / RECIPE_FILES["hooks"]).read_text()
    block = text[text.index("id: bd-dolt-push") :]
    line = next(ln for ln in block.splitlines() if ln.strip().startswith("entry:"))
    return line.split("entry:", 1)[1].strip()


def _run_hook(repo: Repo, bd_exit: int, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    repo.fake_tool(repo.bin_dir / "bd", "")
    (repo.bin_dir / "bd").write_text(f"#!/bin/sh\nexit {bd_exit}\n")
    entry = _dolt_push_entry()
    assert entry.startswith("sh -c '"), entry
    script = entry.removeprefix("sh -c '").removesuffix("'")
    return subprocess.run(["sh", "-c", script], env={**repo.env, **env}, capture_output=True, text=True, check=False)


def test_a_failed_dolt_push_fails_the_push(repo: Repo) -> None:
    result = _run_hook(repo, 1, {})
    assert result.returncode != 0
    assert "FAILED" in result.stderr


def test_a_dolt_push_may_be_skipped_only_by_saying_so(repo: Repo) -> None:
    result = _run_hook(repo, 1, {"BD_DOLT_PUSH_OPTIONAL": "1"})
    assert result.returncode == 0
    assert "FAILED" in result.stderr


def test_a_good_dolt_push_passes(repo: Repo) -> None:
    assert _run_hook(repo, 0, {}).returncode == 0
