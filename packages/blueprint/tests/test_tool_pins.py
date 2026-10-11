"""Tool pins: every tool the repo runs is pinned exactly in mise.toml, locked, and installed at that version (ADR 0024)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_LOCK = """lockfile_version = 3

[[tools.prek]]
version = "0.5.5"

[[tools."github:gastownhall/beads"]]
version = "1.3.1"

[[tools.just]]
version = "1.58.0"
"""
_PINS = '[tools]\nprek = "0.5.5"\njust = "1.58.0"\n"github:gastownhall/beads" = { version = "1.3.1", bin = "bd" }\n'
_JUSTFILE = "check:\n    true\n\ntools:\n    mise install --locked\n"


def _rows(repo: Repo, *, audit: bool = False) -> dict[str, tuple[Verdict, str]]:
    report = run(repo.root, concern="stack", audit=audit, env=repo.env)
    return {r.id: (r.verdict, r.evidence) for r in report.rows if r.id in {"stack.tool-pins", "stack.tools-installed"}}


def _tools_repo(repo: Repo, pins: str = _PINS, lock: str = _LOCK) -> None:
    repo.write(".beads/config.yaml", "")
    repo.write(".pre-commit-config.yaml", "repos: []\n")
    repo.write("justfile", _JUSTFILE)
    repo.write("mise.toml", pins)
    repo.write("mise.lock", lock)


def _pins(repo: Repo) -> tuple[Verdict, str]:
    return _rows(repo)["stack.tool-pins"]


def test_a_repo_with_no_tools_to_pin_is_not_applicable(repo: Repo) -> None:
    assert _pins(repo)[0] is Verdict.NOT_APPLICABLE


def test_no_mise_toml_is_not_set_up_and_names_the_tools(repo: Repo) -> None:
    _tools_repo(repo)
    (repo.root / "mise.toml").unlink()
    verdict, evidence = _pins(repo)
    assert verdict is Verdict.NOT_SET_UP
    assert "bd" in evidence
    assert "prek" in evidence


def test_exact_pins_locked_with_an_install_recipe_pass(repo: Repo) -> None:
    _tools_repo(repo)
    assert _pins(repo)[0] is Verdict.PASSING


def test_latest_or_a_prefix_is_not_a_pin(repo: Repo) -> None:
    _tools_repo(repo, _PINS.replace('prek = "0.5.5"', 'prek = "latest"').replace('just = "1.58.0"', 'just = "1.58"'))
    verdict, evidence = _pins(repo)
    assert verdict is Verdict.FAILING
    assert "prek 'latest'" in evidence
    assert "just '1.58'" in evidence


def test_a_tool_the_repo_runs_but_does_not_pin_fails(repo: Repo) -> None:
    _tools_repo(repo, '[tools]\nprek = "0.5.5"\njust = "1.58.0"\n')
    verdict, evidence = _pins(repo)
    assert verdict is Verdict.FAILING
    assert "bd is not pinned" in evidence


def test_a_pin_missing_from_the_lock_fails(repo: Repo) -> None:
    _tools_repo(repo, lock=_LOCK.replace('version = "0.5.5"', 'version = "0.5.4"'))
    verdict, evidence = _pins(repo)
    assert verdict is Verdict.FAILING
    assert "mise.lock" in evidence
    (repo.root / "mise.lock").unlink()
    assert "no mise.lock" in _pins(repo)[1]


def test_no_recipe_installing_the_lock_fails(repo: Repo) -> None:
    _tools_repo(repo)
    repo.write("justfile", "check:\n    true\n")
    verdict, evidence = _pins(repo)
    assert verdict is Verdict.FAILING
    assert "mise install --locked" in evidence


def test_just_from_the_rust_just_dev_dependency_is_not_pinned_again(repo: Repo) -> None:
    _tools_repo(repo, _PINS.replace('just = "1.58.0"\n', ""))
    repo.write("pyproject.toml", '[project]\nname = "x"\nversion = "0"\n\n[dependency-groups]\ndev = ["rust-just==1.58.0"]\n')
    assert _pins(repo)[0] is Verdict.PASSING
    _tools_repo(repo)
    verdict, evidence = _pins(repo)
    assert verdict is Verdict.FAILING
    assert "just is pinned twice" in evidence


def test_python_and_dotnet_stay_with_their_own_pin_files(repo: Repo) -> None:
    _tools_repo(repo, _PINS + 'python = "3.12.9"\ndotnet = "10.0.401"\n')
    repo.write(".python-version", "3.12\n")
    repo.write("global.json", '{"sdk": {"version": "10.0.401"}}\n')
    verdict, evidence = _pins(repo)
    assert verdict is Verdict.FAILING
    assert ".python-version" in evidence
    assert "global.json" in evidence


def test_the_uv_pin_must_meet_uvs_required_version(repo: Repo) -> None:
    _tools_repo(repo, _PINS + 'uv = "0.9.0"\n', _LOCK + '\n[[tools.uv]]\nversion = "0.9.0"\n')
    repo.write("pyproject.toml", '[project]\nname = "x"\nversion = "0"\n\n[tool.uv]\nrequired-version = ">=0.10.12"\n')
    repo.write("uv.lock", "")
    verdict, evidence = _pins(repo)
    assert verdict is Verdict.FAILING
    assert "required-version" in evidence


def test_the_godot_pin_must_equal_the_csproj_sdk(repo: Repo) -> None:
    godot = '[tools."github:godotengine/godot"]\nversion = "4.7.1-stable"\nrename_exe = "godot"\n'
    _tools_repo(repo, _PINS + godot, _LOCK + '\n[[tools."github:godotengine/godot"]]\nversion = "4.7.1-stable"\n')
    repo.write("src/Game/project.godot", 'config/features=PackedStringArray("4.7", "C#")\n')
    repo.write("src/Game/Game.csproj", '<Project Sdk="Godot.NET.Sdk/4.7.2"></Project>\n')
    verdict, evidence = _pins(repo)
    assert verdict is Verdict.FAILING
    assert "Godot.NET.Sdk/4.7.2" in evidence


def test_an_installed_tool_at_another_version_fails_the_audit(repo: Repo) -> None:
    _tools_repo(repo)
    repo.fake_tool(repo.bin_dir / "bd", "bd version 1.1.2 (dev)")
    repo.fake_tool(repo.bin_dir / "prek", "prek 0.5.5")
    repo.fake_tool(repo.bin_dir / "just", "just 1.58.0")
    verdict, evidence = _rows(repo, audit=True)["stack.tools-installed"]
    assert verdict is Verdict.FAILING
    assert "bd 1.1.2" in evidence
    assert "prek" not in evidence
    repo.fake_tool(repo.bin_dir / "bd", "bd version 1.3.1 (dev)")
    assert _rows(repo, audit=True)["stack.tools-installed"][0] is Verdict.PASSING


def test_the_installed_versions_are_audit_only(repo: Repo) -> None:
    _tools_repo(repo)
    assert "stack.tools-installed" not in _rows(repo)


def test_a_gate_that_runs_gitleaks_must_pin_it(repo: Repo) -> None:
    _tools_repo(repo)
    repo.write("justfile", _JUSTFILE.replace("check:\n    true\n", "check:\n    gitleaks git --no-banner\n"))
    verdict, evidence = _pins(repo)
    assert verdict is Verdict.FAILING
    assert "gitleaks is not pinned" in evidence


def test_a_justfile_comment_naming_gitleaks_does_not_need_a_pin(repo: Repo) -> None:
    _tools_repo(repo)
    repo.write("justfile", "# All prek hooks over every file (ruff, shellcheck, gitleaks).\n" + _JUSTFILE)
    assert _pins(repo)[0] is Verdict.PASSING
