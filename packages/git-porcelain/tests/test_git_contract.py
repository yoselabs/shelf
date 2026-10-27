"""The Git contract, stated once and run against RealGit (temp repos) and FakeGit (memory).

Every scenario in ``features/git_contract.feature`` runs twice: the same steps, the same expected values.
A behaviour FakeGit has is one the git binary showed, so the fake cannot drift. This suite and any
``@smoke`` test are the only tests that touch real git for this API.
"""

from __future__ import annotations

import ast
import hashlib
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import pytest
from git_porcelain import FileStat, Git, GitError, Identity, RealGit, RemoteError, StatusEntry, Worktree
from git_porcelain.testing import FakeGit, FakeRemote, apply_hermetic_env
from git_porcelain.testing import git as run
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/git_contract.feature")

_ME = Identity("Contract Author", "author@example.invalid")
_PLACEHOLDER = re.compile(r"<(\w+)(?::([^>]*))?>")
_FILE = re.compile(r'(\S+?)="((?:[^"\\]|\\.)*)"')


# -- the two ways to arrange a repository -----------------------------------------------------------------
class Rig(Protocol):
    root: Path

    def init(self, name: str) -> Git: ...
    def write(self, repo: Git, rel: str, text: str) -> None: ...
    def remove(self, repo: Git, rel: str) -> None: ...
    def read(self, repo: Git, rel: str) -> str | None: ...
    def set_config(self, repo: Git, key: str, value: str) -> None: ...
    def make_origin(self, name: str) -> str: ...
    def add_remote(self, repo: Git, name: str, url: str) -> None: ...
    def clone(self, url: str, name: str) -> Git: ...
    def drop_checkout(self, repo: Git, path: Path) -> None: ...
    def plain_folder(self, name: str) -> Path: ...


class RealRig:
    """Real git, in folders under ``root``; the hermetic env is the caller's."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def init(self, name: str) -> Git:
        path = self.root / name
        path.mkdir()
        run(path, "init", "-q", "-b", "main")
        return RealGit(path)

    def write(self, repo: Git, rel: str, text: str) -> None:
        target = repo.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def remove(self, repo: Git, rel: str) -> None:
        (repo.path / rel).unlink()

    def read(self, repo: Git, rel: str) -> str | None:
        target = repo.path / rel
        return target.read_text(encoding="utf-8") if target.exists() else None

    def set_config(self, repo: Git, key: str, value: str) -> None:
        run(repo.path, "config", key, value)
        repo.invalidate()

    def make_origin(self, name: str) -> str:
        path = self.root / f"{name}.git"
        run(self.root, "init", "-q", "--bare", "-b", "main", str(path))
        return str(path)

    def add_remote(self, repo: Git, name: str, url: str) -> None:
        run(repo.path, "remote", "add", name, url)
        repo.invalidate()

    def clone(self, url: str, name: str) -> Git:
        run(self.root, "clone", "-q", url, name)
        return RealGit(self.root / name)

    def drop_checkout(self, repo: Git, path: Path) -> None:
        shutil.rmtree(path)

    def plain_folder(self, name: str) -> Path:
        path = self.root / name
        path.mkdir()
        return path


class FakeRig:
    """FakeGit in memory; ``root`` is only a name space for paths."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._origins: dict[str, FakeRemote] = {}

    def init(self, name: str) -> Git:
        return FakeGit.init(self.root / name)

    def write(self, repo: Git, rel: str, text: str) -> None:
        assert isinstance(repo, FakeGit)
        repo.write_file(rel, text)

    def remove(self, repo: Git, rel: str) -> None:
        assert isinstance(repo, FakeGit)
        repo.remove_file(rel)

    def read(self, repo: Git, rel: str) -> str | None:
        assert isinstance(repo, FakeGit)
        return repo.read_file(rel)

    def set_config(self, repo: Git, key: str, value: str) -> None:
        assert isinstance(repo, FakeGit)
        repo.set_config(key, value)

    def make_origin(self, name: str) -> str:
        url = str(self.root / f"{name}.git")
        self._origins[url] = FakeRemote(url)
        return url

    def add_remote(self, repo: Git, name: str, url: str) -> None:
        assert isinstance(repo, FakeGit)
        repo.add_remote(name, self._origins[url])

    def clone(self, url: str, name: str) -> Git:
        return FakeGit.clone(self._origins[url], self.root / name)

    def drop_checkout(self, repo: Git, path: Path) -> None:
        assert isinstance(repo, FakeGit)
        repo.drop_checkout(path)

    def plain_folder(self, name: str) -> Path:
        return self.root / name


@dataclass
class World:
    rig: Rig
    repos: dict[str, Git] = field(default_factory=dict)
    memory: dict[str, str] = field(default_factory=dict)
    result: object = None
    error: Exception | None = None


@pytest.fixture(params=["real", "fake"], autouse=True)
def implementation(request: pytest.FixtureRequest) -> str:
    """Every scenario of this module runs once per implementation."""
    return str(request.param)


@pytest.fixture
def world(implementation: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    apply_hermetic_env(monkeypatch, identity=_ME, home=tmp_path / "home")
    return World(RealRig(tmp_path) if implementation == "real" else FakeRig(tmp_path))


def _text(raw: str) -> str:
    return raw.replace("\\n", "\n")


def _expand(world: World, raw: str) -> str:
    def value(match: re.Match[str]) -> str:
        kind, arg = match.group(1), match.group(2) or ""
        if kind == "root":
            return str(world.rig.root)
        if kind == "head":
            return world.repos[arg].head() or ""
        if kind == "tree":
            return world.repos[arg].tree_hash()
        if kind == "mem":
            return world.memory[arg]
        if kind == "blob":
            data = _text(arg).encode()
            return hashlib.sha1(f"blob {len(data)}".encode() + b"\0" + data, usedforsecurity=False).hexdigest()[:7]
        return match.group(0)

    return _PLACEHOLDER.sub(value, raw)


def _plain(item: object) -> object:
    if isinstance(item, StatusEntry):
        return f"{item.code} {item.path}" + (f" <- {item.orig_path}" if item.orig_path else "")
    if isinstance(item, Worktree):
        return f"{item.path} {item.branch or '(detached)'}"
    if isinstance(item, FileStat):
        return f"{item.path} +{item.added} -{item.deleted}"
    if isinstance(item, set):
        return sorted(_plain(i) for i in item)  # type: ignore[type-var]
    if isinstance(item, list):
        return [_plain(i) for i in item]
    return str(item) if hasattr(item, "parts") else item


def _call(world: World, name: str, call: str) -> object:
    node = ast.parse(_expand(world, call), mode="eval").body
    assert isinstance(node, ast.Call)
    assert isinstance(node.func, ast.Name)
    args = [ast.literal_eval(a) for a in node.args]
    kwargs = {k.arg: ast.literal_eval(k.value) for k in node.keywords if k.arg}
    if node.func.id == "worktree_remove":
        args[0] = Path(args[0])
    return getattr(world.repos[name], node.func.id)(*args, **kwargs)


# -- arranging -----------------------------------------------------------------------------------------
@given(parsers.parse('a repository "{name}"'))
def _repository(world: World, name: str) -> None:
    world.repos[name] = world.rig.init(name)


@given(parsers.parse('an origin "{name}"'))
def _origin(world: World, name: str) -> None:
    world.memory[f"origin:{name}"] = world.rig.make_origin(name)


@given(parsers.parse('"{name}" has the origin "{origin}" as remote "{remote}"'))
def _add_remote(world: World, name: str, origin: str, remote: str) -> None:
    world.rig.add_remote(world.repos[name], remote, world.memory[f"origin:{origin}"])


@given(parsers.parse('"{name}" is a clone of the origin "{origin}"'))
def _clone(world: World, name: str, origin: str) -> None:
    world.repos[name] = world.rig.clone(world.memory[f"origin:{origin}"], name)


@given(parsers.parse('"{name}" is the plain folder'))
def _plain_folder(world: World, name: str) -> None:
    world.repos[name] = _bare_view(world, name)


def _bare_view(world: World, name: str) -> Git:
    anchor = world.rig.init(f"{name}-anchor")
    return anchor.at(world.rig.plain_folder(name))


@given(parsers.parse('"{name}" config "{key}" is "{value}"'))
def _config(world: World, name: str, key: str, value: str) -> None:
    world.rig.set_config(world.repos[name], key, value)


@given(parsers.parse('"{name}" commits "{message}" with {files}'))
@when(parsers.parse('"{name}" commits "{message}" with {files}'))
def _commit_with(world: World, name: str, message: str, files: str) -> None:
    repo = world.repos[name]
    for rel, text in _FILE.findall(files):
        world.rig.write(repo, rel, _text(text))
    repo.add()
    repo.commit(message)


@given(parsers.parse('"{name}" writes {files}'))
@when(parsers.parse('"{name}" writes {files}'))
def _writes(world: World, name: str, files: str) -> None:
    for rel, text in _FILE.findall(files):
        world.rig.write(world.repos[name], rel, _text(text))


@given(parsers.parse('"{name}" removes "{rel}"'))
@when(parsers.parse('"{name}" removes "{rel}"'))
def _removes(world: World, name: str, rel: str) -> None:
    world.rig.remove(world.repos[name], rel)


@given(parsers.parse('"{name}" remembers its head as "{label}"'))
@when(parsers.parse('"{name}" remembers its head as "{label}"'))
def _remember(world: World, name: str, label: str) -> None:
    world.memory[label] = world.repos[name].head() or ""


@given(parsers.parse('"{name}" calls {call}'))
@when(parsers.parse('"{name}" calls {call}'))
def _calls(world: World, name: str, call: str) -> None:
    world.result = _call(world, name, call)


@given(parsers.parse('"{name}" adds a worktree "{rel}" at "{rev}" as "{label}"'))
@when(parsers.parse('"{name}" adds a worktree "{rel}" at "{rev}" as "{label}"'))
def _worktree(world: World, name: str, rel: str, rev: str, label: str) -> None:
    world.repos[label] = world.repos[name].worktree_add(world.rig.root / rel, rev)


@when(parsers.parse('"{name}" tries {call}'))
def _tries(world: World, name: str, call: str) -> None:
    try:
        world.result = _call(world, name, call)
    except GitError as exc:
        world.error = exc


@when(parsers.parse('the folder of "{name}" is deleted behind git\'s back'))
def _drop(world: World, name: str) -> None:
    repo = world.repos[name]
    world.rig.drop_checkout(repo, repo.path)


# -- checking ------------------------------------------------------------------------------------------
@then(parsers.parse("the result is {expected}"))
def _result_is(world: World, expected: str) -> None:
    assert _plain(world.result) == ast.literal_eval(_expand(world, expected))


@then("the result looks like a sha")
def _result_sha(world: World) -> None:
    assert isinstance(world.result, str)
    assert re.fullmatch(r"[0-9a-f]{40}", world.result)


@then(parsers.parse('the file "{rel}" of "{name}" holds "{text}"'))
def _file_holds(world: World, name: str, rel: str, text: str) -> None:
    assert world.rig.read(world.repos[name], rel) == _text(text)


@then(parsers.parse('the file "{rel}" of "{name}" is absent'))
def _file_absent(world: World, name: str, rel: str) -> None:
    assert world.rig.read(world.repos[name], rel) is None


@then(parsers.parse('the tree hash of "{name}" equals the tree hash of "{other}"'))
def _same_tree(world: World, name: str, other: str) -> None:
    assert world.repos[name].tree_hash() == world.repos[other].tree_hash()


@then(parsers.parse('the file "{rel}" of "{name}" has conflict markers'))
def _file_markers(world: World, name: str, rel: str) -> None:
    content = world.rig.read(world.repos[name], rel) or ""
    assert "<<<<<<<" in content
    assert "=======" in content
    assert ">>>>>>>" in content


@then("the call fails")
def _fails(world: World) -> None:
    assert isinstance(world.error, GitError)


@then(parsers.parse('the call fails as a remote error because "{reason}"'))
def _fails_remote(world: World, reason: str) -> None:
    assert isinstance(world.error, RemoteError)
    assert world.error.reason == reason
