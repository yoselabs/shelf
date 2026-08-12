"""The commit guard, tested — it had no automated coverage until now.

`forbid-local-shelf-source.py` is the one thing standing between a co-development
override and a poisoned consumer checkout, and it was verified exactly once, by
hand, against scratch repos that were deleted afterwards (ledger 0038). This
suite is that verification made repeatable.

The tests build real git repositories rather than mocking `git`, because every
bug this session found in guard tooling was a wrong belief about what git does
(`core.hooksPath` resolution, index vs HEAD vs working tree). A mock would have
confirmed the wrong belief.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[1] / "tools" / "hooks" / "forbid-local-shelf-source.py"

_LOCAL_SOURCE = """\
[project]
name = "consumer"
version = "0.1.0"

[tool.uv.sources]
anyllm = { path = "../shelf/packages/anyllm", editable = true }
"""

_PINNED_SOURCE = """\
[project]
name = "consumer"
version = "0.1.0"

[tool.uv.sources]
anyllm = { git = "https://github.com/yoselabs/shelf", subdirectory = "packages/anyllm", tag = "anyllm-v0.1.0" }
"""

_UNRELATED_LOCAL = """\
[project]
name = "consumer"
version = "0.1.0"

[tool.uv.sources]
some-sibling = { path = "../some-sibling", editable = true }
"""


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A real git repo with identity configured, no commits yet."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "Test")
    return tmp_path


def _run(repo: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GUARD), *flags],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def _commit(repo: Path, content: str) -> None:
    (repo / "pyproject.toml").write_text(content)
    _git(repo, "add", "pyproject.toml")
    _git(repo, "commit", "-qm", "pyproject")


def test_staged_local_shelf_source_is_refused(repo: Path) -> None:
    """The hook's question: this is about to be committed."""
    (repo / "pyproject.toml").write_text(_LOCAL_SOURCE)
    _git(repo, "add", "pyproject.toml")

    result = _run(repo)

    assert result.returncode == 1
    assert "anyllm" in result.stderr


def test_staged_git_tag_pin_passes(repo: Path) -> None:
    (repo / "pyproject.toml").write_text(_PINNED_SOURCE)
    _git(repo, "add", "pyproject.toml")

    assert _run(repo).returncode == 0


def test_committed_local_shelf_source_is_caught_by_the_gate(repo: Path) -> None:
    """The gate's question: this already landed, and every clone carries it."""
    _commit(repo, _LOCAL_SOURCE)

    result = _run(repo, "--committed")

    assert result.returncode == 1
    assert "anyllm" in result.stderr


def test_committed_git_tag_pin_passes_the_gate(repo: Path) -> None:
    _commit(repo, _PINNED_SOURCE)

    assert _run(repo, "--committed").returncode == 0


def test_uncommitted_override_does_not_fail_the_gate(repo: Path) -> None:
    """The co-development workflow the docs prescribe must keep working.

    `docs/consuming-the-shelf.md` §1 tells you to use an *uncommitted* local
    override for co-developing shelf and a consumer. A gate that read the working
    tree would fail on exactly that, breaking the supported workflow — so the gate
    reads HEAD, and this is the test that pins the distinction.
    """
    _commit(repo, _PINNED_SOURCE)
    (repo / "pyproject.toml").write_text(_LOCAL_SOURCE)  # dirty working tree, nothing staged

    assert _run(repo, "--committed").returncode == 0


def test_staged_override_still_blocked_even_though_the_gate_allows_it_uncommitted(repo: Path) -> None:
    """The two modes disagree on purpose: staging it is the moment it becomes an offense."""
    _commit(repo, _PINNED_SOURCE)
    (repo / "pyproject.toml").write_text(_LOCAL_SOURCE)
    _git(repo, "add", "pyproject.toml")

    assert _run(repo, "--committed").returncode == 0
    assert _run(repo).returncode == 1


def test_unrelated_local_sibling_dependency_is_left_alone(repo: Path) -> None:
    """Only shelf-referencing local sources are the guard's business."""
    _commit(repo, _UNRELATED_LOCAL)

    assert _run(repo, "--committed").returncode == 0


def test_repo_with_no_commits_is_clean(repo: Path) -> None:
    """Nothing committed cannot have poisoned anything."""
    assert _run(repo, "--committed").returncode == 0


def test_head_without_a_pyproject_is_clean(repo: Path) -> None:
    (repo / "README.md").write_text("no pyproject here\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "readme")

    assert _run(repo, "--committed").returncode == 0


def test_outside_a_git_repo_reports_could_not_check_not_success(tmp_path: Path) -> None:
    """The lesson of this whole session: "couldn't check" must never look like "checked".

    A guard that exits 0 when it could not run is how a dead guard reported green.
    """
    result = _run(tmp_path, "--committed")

    assert result.returncode == 2
    assert "NOT a pass" in result.stderr


def test_malformed_toml_reports_could_not_check_not_a_crash(repo: Path) -> None:
    """Found for real (shelf-jmm): a duplicate [tool.uv.sources] table is invalid TOML.

    `tomllib.loads` raised uncaught, so this printed a raw Python traceback instead
    of the guard's own message -- accidentally fail-closed (an uncaught exception
    exits 1, same as "offenders found"), not fail-open, but unintentional and
    untested. Malformed content is "could not check", same family as "not a git
    repository" above -- never a silent pass, and never a crash either.
    """
    _commit(repo, '[tool.uv.sources]\nanyllm = { git = "x" }\n\n[tool.uv.sources]\nother = { git = "y" }\n')

    result = _run(repo, "--committed")

    assert result.returncode == 2
    assert "NOT a pass" in result.stderr
    assert "Traceback" not in result.stderr
    assert "not valid TOML" in result.stderr
