"""The `beads` operation: `bd init --skip-hooks`, the strict settings with readback, session settings.

Uses the real `bd` binary against real temp git repos.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "tools"))

import onboard.beads as beads_mod  # noqa: E402  -- path-injected, after sys.path setup
from onboard.beads import BeadsOperation  # noqa: E402
from onboard.operations import Outcome  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("bd") is None, reason="bd is not installed")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "Test")
    (r / "AGENTS.md").write_text("# Project\n")
    _git(r, "add", "AGENTS.md")
    _git(r, "commit", "-qm", "init")
    return r


def test_initializes_without_hooks_and_reads_back_the_strict_set(repo: Path) -> None:
    result = BeadsOperation(repo).run({})
    assert result.outcome == Outcome.APPLIED, result.message
    assert "strict settings in .beads/config.yaml" in result.message
    hooks_path = subprocess.run(
        ["git", "-C", str(repo), "config", "--local", "core.hooksPath"], capture_output=True, text=True, check=False
    )
    assert hooks_path.stdout.strip() == "", "bd took over core.hooksPath despite --skip-hooks"
    assert not any("BEGIN BEADS" in p.read_text(errors="replace") for p in (repo / ".git" / "hooks").iterdir() if p.is_file())
    for key, value in (("validation.on-create", "error"), ("export.auto", "false"), ("no-git-ops", "true")):
        got = subprocess.run(["bd", "config", "get", key], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
        assert got == value, key


def test_session_settings_are_merged_not_overwritten(repo: Path) -> None:
    settings = repo / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"env": {"KEEP": "1"}, "permissions": {"allow": ["Bash"]}}))
    BeadsOperation(repo).run({})
    data = json.loads(settings.read_text())
    assert data["env"] == {"KEEP": "1", "BD_DISABLE_METRICS": "1"}
    assert data["permissions"] == {"allow": ["Bash"]}
    assert "bd prime" in json.dumps(data["hooks"]["SessionStart"])
    assert "in_progress" in json.dumps(data["hooks"]["Stop"])


def test_second_run_is_idempotent(repo: Path) -> None:
    BeadsOperation(repo).run({})
    first = (repo / ".claude" / "settings.json").read_text()
    again = BeadsOperation(repo).run({})
    assert again.outcome == Outcome.APPLIED, again.message
    assert (repo / ".claude" / "settings.json").read_text() == first


def test_config_readback_mismatch_is_reported_not_silently_trusted(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A write that does not reach config.yaml is a failure, not a pass."""

    def _writes_nothing(*_args: object) -> None:
        return None

    monkeypatch.setattr(beads_mod, "_write_strict", _writes_nothing)
    result = BeadsOperation(repo).run({})
    assert result.outcome == Outcome.FAILED
    assert "readback mismatch" in result.message


def test_the_blueprint_backlog_concern_passes_after_the_operation(repo: Path) -> None:
    """a2peer: the operation left export.auto/export.git-add true and import.auto in bd's database, so the audit failed."""
    assert BeadsOperation(repo).run({}).outcome == Outcome.APPLIED
    sys.path.insert(0, str(_ROOT / "packages" / "blueprint" / "src"))
    from blueprint.model import Verdict  # noqa: PLC0415 -- path-injected above
    from blueprint.runner import run  # noqa: PLC0415

    rows = {r.id: r for r in run(repo, concern="backlog", audit=True).rows}
    assert rows["backlog.strict-config"].verdict is Verdict.PASSING, rows["backlog.strict-config"].evidence
    config = (repo / ".beads" / "config.yaml").read_text()
    assert "auto: true" not in config
    assert "git-add: true" not in config


_BD_CONFIG = """# Beads Configuration File
# export:
#   auto: false

export:
    auto: true
    path: issues.jsonl
    git-add: true

# trailing comment
issue-prefix: keep
"""


@pytest.mark.parametrize(
    ("text", "values", "present", "absent"),
    [
        # a2peer: bd wrote export.auto/git-add true; both become false, the neighbours stay
        (
            _BD_CONFIG,
            {"export.auto": "false", "export.git-add": "false"},
            ["    auto: false", "    git-add: false", "    path: issues.jsonl", "issue-prefix: keep", "# trailing comment"],
            ["auto: true", "git-add: true"],
        ),
        # a key under a missing parent is created nested
        ("no-git-ops: true\n", {"import.auto": "false"}, ["import:", "    auto: false", "no-git-ops: true"], []),
        # a missing child joins its existing parent block, not the end of the file
        ("export:\n    path: x\n\nissue-prefix: p\n", {"export.git-add": "false"}, ["    path: x\n    git-add: false\n"], []),
        # a top-level key is replaced in place
        ("no-git-ops: false\n", {"no-git-ops": "true"}, ["no-git-ops: true"], ["false"]),
        # three levels deep
        ("validation:\n    metadata:\n        mode: warn\n", {"validation.metadata.mode": "error"}, ["        mode: error"], ["warn"]),
        ("", {"validation.on-create": "error"}, ["validation:\n    on-create: error\n"], []),
    ],
)
def test_the_yaml_editor_sets_dotted_keys_and_keeps_the_rest(
    text: str, values: dict[str, str], present: list[str], absent: list[str]
) -> None:
    out = beads_mod.set_yaml_keys(text, values)
    assert all(p in out for p in present), out
    assert not any(a in out for a in absent), out
    assert beads_mod.set_yaml_keys(out, values) == out, "not idempotent"


def test_a_scalar_where_a_block_is_needed_is_refused_not_clobbered() -> None:
    with pytest.raises(ValueError, match="not a block"):
        beads_mod.set_yaml_keys("export: {auto: true}\n", {"export.auto": "false"})
