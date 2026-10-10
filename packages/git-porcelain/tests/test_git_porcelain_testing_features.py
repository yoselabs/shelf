"""git_porcelain.testing, stated as Gherkin."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from git_porcelain import Identity
from git_porcelain.testing import apply_hermetic_env, git
from pytest_bdd import given, parsers, scenarios, then, when

if TYPE_CHECKING:
    from pathlib import Path

scenarios("features/hermetic_env.feature")


@dataclass
class World:
    root: Path
    repo: Path
    failure: AssertionError | None = None


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(root=tmp_path, repo=tmp_path / "repo")


def _hook(folder: Path, marker: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    hook = folder / "pre-commit"
    hook.write_text(f"#!/bin/sh\necho ran >> '{marker}'\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    return folder


@given('the machine\'s global git config names "Leaked Name" and runs a failing pre-commit hook')
def _machine(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    home = world.root / "home"
    hooks = _hook(home / "hooks", world.root / "machine-hook-ran")
    home.mkdir(exist_ok=True)
    (home / ".gitconfig").write_text(
        f"[user]\n\tname = Leaked Name\n\temail = leak@example.invalid\n[core]\n\thooksPath = {hooks}\n", encoding="utf-8"
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / ".gitconfig"))


@given("a variable points git at another repository")
def _leak(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_DIR", str(world.root / "elsewhere" / ".git"))


@given(parsers.parse('the hermetic git env with the identity "{name}"'))
def _with_identity(world: World, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    apply_hermetic_env(monkeypatch, identity=Identity(name, "author@example.invalid"), home=world.root / "home")


@given("the hermetic git env with no identity")
def _no_identity(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    apply_hermetic_env(monkeypatch, home=world.root / "home")


@given(parsers.parse('the hermetic git env with the identity "{name}" and no quiet settings'))
def _loud(world: World, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    apply_hermetic_env(monkeypatch, identity=Identity(name, "author@example.invalid"), config={})


@given("the repository runs a pre-commit hook that refuses")
def _refusing_hook(world: World) -> None:
    world.repo.mkdir()
    git(world.repo, "init", "-q", "-b", "main")
    _hook(world.repo / ".git" / "hooks", world.root / "repo-hook-ran")


@when("a repository is made")
def _made(world: World) -> None:
    world.repo.mkdir(exist_ok=True)
    git(world.repo, "init", "-q", "-b", "main")


@when("a repository is made and a file committed")
def _committed(world: World) -> None:
    _made(world)
    (world.repo / "a.md").write_text("a\n", encoding="utf-8")
    git(world.repo, "add", "a.md")
    try:
        git(world.repo, "commit", "-qm", "first")
    except AssertionError as exc:
        world.failure = exc


@when(parsers.parse('git runs "{command}" in a folder'))
def _runs(world: World, command: str) -> None:
    world.repo.mkdir()
    try:
        git(world.repo, command)
    except AssertionError as exc:
        world.failure = exc


@then(parsers.parse('the commit\'s author is "{name}"'))
def _author(world: World, name: str) -> None:
    assert world.failure is None, world.failure
    assert git(world.repo, "show", "-s", "--format=%an").strip() == name


@then("no hook ran")
def _no_hook(world: World) -> None:
    assert not (world.root / "machine-hook-ran").exists()


@then(parsers.parse('git config "{key}" is unset'))
def _unset(world: World, key: str) -> None:
    with pytest.raises(AssertionError):
        git(world.repo, "config", key)


@then("the commit fails")
def _commit_fails(world: World) -> None:
    assert world.failure is not None


@then("the repository's hook ran")
def _repo_hook(world: World) -> None:
    assert (world.root / "repo-hook-ran").exists()


@then(parsers.parse('the command fails naming "{text}"'))
def _fails(world: World, text: str) -> None:
    assert world.failure is not None
    assert text in str(world.failure)
