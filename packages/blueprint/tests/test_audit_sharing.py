"""One audit run asks the repo each question once: a file is read once, a git query runs once, the plugin manifests parse once.

A file open and a process start cost about 20 ms each under a file scanner (`any-gate steps --opens`), and the audit asked the same
question hundreds of times (shelf, 2026-11-27: 182 reads of every plugin manifest, 7 to 39 reads of each pyproject.toml).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from blueprint import plugins
from blueprint.model import Context, Profile
from blueprint.runner import run

if TYPE_CHECKING:
    import subprocess

    import pytest
    from blueprint.testing import Repo


def _ctx(repo: Repo) -> Context:
    return Context(repo.root, Profile("library", (), (), (), None), env=repo.env)


def test_a_file_is_read_once_per_run(repo: Repo, monkeypatch: pytest.MonkeyPatch) -> None:
    repo.write("a.toml", 'x = "1"\n')
    reads: list[Path] = []
    original = Path.read_text

    def counting(self: Path, *args: Any, **kwargs: Any) -> str:
        reads.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting)
    ctx = _ctx(repo)
    assert ctx.read("a.toml") == ctx.read("a.toml") == 'x = "1"\n'
    assert ctx.toml("a.toml") == {"x": "1"}
    assert ctx.read("absent.toml") is None
    assert ctx.read("absent.toml") is None
    assert [p.name for p in reads] == ["a.toml"]


def test_a_toml_answer_is_not_shared_between_callers(repo: Repo) -> None:
    repo.write("a.toml", 'x = "1"\n')
    ctx = _ctx(repo)
    ctx.toml("a.toml")["x"] = "changed"
    assert ctx.toml("a.toml") == {"x": "1"}


def test_a_git_query_runs_once_per_run(repo: Repo) -> None:
    ctx = _ctx(repo)
    calls: list[tuple[str, ...]] = []
    original = ctx.run

    def counting(*argv: str, **kwargs: Any) -> subprocess.CompletedProcess[str] | None:
        calls.append(argv)
        return original(*argv, **kwargs)

    ctx.run = counting
    first = ctx.git("rev-parse", "--git-dir")
    assert first is not None
    assert ctx.git("rev-parse", "--git-dir") == first
    assert ctx.git("rev-parse", "--git-path", "hooks") is not None
    assert calls == [("git", "rev-parse", "--git-dir"), ("git", "rev-parse", "--git-path", "hooks")]


def test_a_failed_git_query_is_remembered_too(repo: Repo) -> None:
    ctx = _ctx(repo)
    calls: list[tuple[str, ...]] = []
    original = ctx.run

    def counting(*argv: str, **kwargs: Any) -> subprocess.CompletedProcess[str] | None:
        calls.append(argv)
        return original(*argv, **kwargs)

    ctx.run = counting
    assert ctx.git("rev-parse", "--verify", "-q", "refs/heads/nope") is None
    assert ctx.git("rev-parse", "--verify", "-q", "refs/heads/nope") is None
    assert len(calls) == 1


def test_the_shipped_plugin_manifests_parse_once_per_process(monkeypatch: pytest.MonkeyPatch) -> None:
    plugins._shipped.cache_clear()
    parsed: list[str] = []
    original = plugins.tomllib.loads

    def counting(text: str) -> dict[str, object]:
        parsed.append(text)
        return original(text)

    monkeypatch.setattr(plugins.tomllib, "loads", counting)
    first = plugins.load_plugins()
    again = plugins.load_plugins()
    assert first == again
    assert first is not again  # a caller may edit what it got
    assert len(parsed) == len(list(plugins.PLUGIN_DIR.glob("*.toml")))
    plugins._shipped.cache_clear()


def test_a_manifest_folder_other_than_the_shipped_one_is_read_every_time(tmp_path: Path) -> None:
    (tmp_path / "x.toml").write_text('id = "x"\ntitle = "X"\ndefault = "on"\nrows = ["x.*"]\n')
    assert set(plugins.load_plugins(tmp_path)) == {"x"}
    (tmp_path / "x.toml").write_text('id = "y"\ntitle = "Y"\ndefault = "on"\nrows = ["y.*"]\n')
    assert set(plugins.load_plugins(tmp_path)) == {"y"}


def test_the_audit_verdicts_do_not_depend_on_the_sharing(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "x"\nversion = "0"\n')
    repo.commit()
    assert run(repo.root, env=repo.env).rows == run(repo.root, env=repo.env).rows
