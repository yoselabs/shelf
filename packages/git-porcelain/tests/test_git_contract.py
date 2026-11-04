"""The Repo/Worktree contract, stated once and run against RealRepo (temp repos) and FakeRepo (memory).

Every scenario in ``features/git_contract.feature`` runs twice: the same steps, the same expected values. A
behaviour FakeRepo has is one the git binary showed, so the fake cannot drift. A scenario tagged ``real_only`` names
a fidelity gap of the fake (conftest.py leaves it out of the fake run). This suite and ``git_real_cache.feature`` are
the only tests that touch real git for this API.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from git_porcelain import Change, CommandResult, GitTimeout, GitUnavailable, Identity, RealRepo, Rebased, Worktree, WorktreeRemoveRefused
from git_porcelain.fake_ops import stage
from git_porcelain.real_done import Done
from git_porcelain.real_parse import parse_status
from git_porcelain.testing import QUIET, FakeRemote, FakeRepo, FakeWorktree, apply_hermetic_env
from git_porcelain.testing import git as run

if TYPE_CHECKING:
    from collections.abc import Mapping

scenarios("features/git_contract.feature")

_ME = Identity("Contract Author", "author@example.invalid")
_PLACEHOLDER = re.compile(r"<(\w+)(?::([^>]*))?>")
_FILE = re.compile(r'("[^"]+"|\S+?)="((?:[^"\\]|\\.)*)"')
_PATH_ARGS = {"add_worktree", "drop_worktree", "release_branch", "worktree_state"}


# -- the two ways to arrange a repository -----------------------------------------------------------------
class Rig(Protocol):
    root: Path
    identity: Identity | None

    def init(self, name: str) -> Worktree: ...
    def write(self, wt: Worktree, rel: str, text: str) -> None: ...
    def remove(self, wt: Worktree, rel: str) -> None: ...
    def read(self, wt: Worktree, rel: str) -> str | None: ...
    def head(self, wt: Worktree) -> str: ...
    def set_config(self, wt: Worktree, key: str, value: str) -> None: ...
    def make_origin(self, name: str) -> str: ...
    def add_remote(self, wt: Worktree, name: str, url: str) -> None: ...
    def clone(self, url: str, name: str) -> Worktree: ...
    def advance_origin(self, url: str, branch: str, files: dict[str, str]) -> None: ...
    def origin_offline(self, url: str, *, offline: bool) -> None: ...
    def drop_checkout(self, wt: Worktree) -> None: ...
    def plain_folder(self, name: str) -> Path: ...
    def sub_folder(self, wt: Worktree, name: str) -> Path: ...
    def hook(self, wt: Worktree, kind: str, mode: str) -> None: ...
    def lock_index(self, wt: Worktree) -> None: ...
    def edit_same_tick(self, wt: Worktree, rel: str, text: str) -> None: ...


class RealRig:
    """Real git, in folders under ``root``; the hermetic env is the caller's."""

    def __init__(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.root = root.resolve()
        self.monkeypatch = monkeypatch
        self.identity: Identity | None = None
        self.locks: list[Path] = []
        self.rests: list[float] = []
        self._advances = 0

    def sleep(self, seconds: float) -> None:
        """RealRepo's sleep between fetch tries: the competing process 'finishes' and lets go of its lock."""
        self.rests.append(seconds)
        for lock in self.locks:
            lock.unlink(missing_ok=True)

    def _repo(self, path: Path) -> Worktree:
        return RealRepo(path, identity=self.identity, sleep=self.sleep).worktree(path)

    def init(self, name: str) -> Worktree:
        path = self.root / name
        path.mkdir()
        run(path, "init", "-q", "-b", "main")
        return self._repo(path)

    def write(self, wt: Worktree, rel: str, text: str) -> None:
        target = wt.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def remove(self, wt: Worktree, rel: str) -> None:
        (wt.path / rel).unlink()

    def read(self, wt: Worktree, rel: str) -> str | None:
        target = wt.path / rel
        return target.read_text(encoding="utf-8") if target.exists() else None

    def head(self, wt: Worktree) -> str:
        return run(wt.path, "rev-parse", "HEAD").strip()

    def set_config(self, wt: Worktree, key: str, value: str) -> None:
        run(wt.path, "config", key, value)

    def make_origin(self, name: str) -> str:
        path = self.root / f"{name}.git"
        run(self.root, "init", "-q", "--bare", "-b", "main", str(path))
        run(path, "config", "receive.denyDeleteCurrent", "ignore")  # the contract deletes main on a bare origin; the fake allows it
        return str(path)

    def add_remote(self, wt: Worktree, name: str, url: str) -> None:
        run(wt.path, "remote", "add", name, url)

    def clone(self, url: str, name: str) -> Worktree:
        run(self.root, "clone", "-q", url, name)
        return self._repo(self.root / name)

    def advance_origin(self, url: str, branch: str, files: dict[str, str]) -> None:
        self._advances += 1
        work = self.root / f"advance-{self._advances}"
        run(self.root, "clone", "-q", url, str(work))
        for rel, text in files.items():
            (work / rel).parent.mkdir(parents=True, exist_ok=True)
            (work / rel).write_text(text, encoding="utf-8")
        run(work, "add", "-A")
        run(work, "commit", "-q", "-m", "advance")
        run(work, "push", "-q", "origin", f"HEAD:refs/heads/{branch}")

    def origin_offline(self, url: str, *, offline: bool) -> None:
        gone = Path(f"{url}.off")
        if offline:
            Path(url).rename(gone)
        else:
            gone.rename(url)

    def drop_checkout(self, wt: Worktree) -> None:
        shutil.rmtree(wt.path)

    def plain_folder(self, name: str) -> Path:
        path = self.root / name
        path.mkdir()
        return path

    def sub_folder(self, wt: Worktree, name: str) -> Path:
        path = wt.path / name
        path.mkdir()
        return path

    def hook(self, wt: Worktree, kind: str, mode: str) -> None:
        # the hermetic env runs with core.hooksPath=/dev/null at command-line scope: hooks only run without it
        config = {k: v for k, v in QUIET.items() if k != "core.hooksPath"}
        apply_hermetic_env(self.monkeypatch, identity=_ME, config=config, home=self.root / "home")
        script = (
            f"echo '{kind} hook declined' >&2\nexit 1\n"
            if mode == "refuses"
            else '[ "$X" = "1" ] || { echo "X is not set" >&2; exit 1; }\n'
        )
        hook = wt.path / ".git" / "hooks" / kind
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text("#!/bin/sh\n" + script, encoding="utf-8")
        hook.chmod(0o755)

    def lock_index(self, wt: Worktree) -> None:
        (wt.path / ".git" / "index.lock").write_text("", encoding="utf-8")

    def edit_same_tick(self, wt: Worktree, rel: str, text: str) -> None:
        target = wt.path / rel
        before = target.stat()
        target.write_text(text, encoding="utf-8")
        os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))


class FakeRig:
    """FakeRepo in memory; ``root`` is only a name space for paths."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.identity: Identity | None = None
        self._origins: dict[str, FakeRemote] = {}

    @staticmethod
    def _wt(wt: Worktree) -> FakeWorktree:
        assert isinstance(wt, FakeWorktree)
        return wt

    @staticmethod
    def _repo(wt: Worktree) -> FakeRepo:
        assert isinstance(wt.repo, FakeRepo)
        return wt.repo

    def init(self, name: str) -> Worktree:
        repo = FakeRepo.init(self.root / name)
        return repo.worktree(repo.path)

    def write(self, wt: Worktree, rel: str, text: str) -> None:
        self._wt(wt).write_file(rel, text)

    def remove(self, wt: Worktree, rel: str) -> None:
        self._wt(wt).remove_file(rel)

    def read(self, wt: Worktree, rel: str) -> str | None:
        return self._wt(wt).read_file(rel)

    def head(self, wt: Worktree) -> str:
        return str(wt.repo.history(["HEAD"], limit=1)[0].sha)

    def set_config(self, wt: Worktree, key: str, value: str) -> None:
        self._repo(wt).set_config(key, value)

    def make_origin(self, name: str) -> str:
        url = str(self.root / f"{name}.git")
        self._origins[url] = FakeRemote(url)
        return url

    def add_remote(self, wt: Worktree, name: str, url: str) -> None:
        self._repo(wt).add_remote(name, self._origins[url])

    def clone(self, url: str, name: str) -> Worktree:
        repo = FakeRepo.clone(self._origins[url], self.root / name)
        return repo.worktree(repo.path)

    def advance_origin(self, url: str, branch: str, files: dict[str, str]) -> None:
        self._origins[url].advance(branch, files)

    def origin_offline(self, url: str, *, offline: bool) -> None:
        self._origins[url].offline = offline

    def drop_checkout(self, wt: Worktree) -> None:
        self._repo(wt).drop_checkout(wt.path)

    def plain_folder(self, name: str) -> Path:
        return self.root / name

    def sub_folder(self, wt: Worktree, name: str) -> Path:
        return wt.path / name

    def hook(self, wt: Worktree, kind: str, mode: str) -> None:
        hooks = self._repo(wt).hooks
        if kind == "pre-commit":
            hooks.refuse_commit = True
        elif mode == "refuses":
            hooks.refuse_push = True
        else:
            hooks.push_requires_env = {"X": "1"}

    def lock_index(self, wt: Worktree) -> None:
        self._wt(wt).lock_index()

    def edit_same_tick(self, wt: Worktree, rel: str, text: str) -> None:
        self.write(wt, rel, text)


@dataclass
class World:
    rig: Rig
    kind: str
    monkeypatch: pytest.MonkeyPatch
    wts: dict[str, Worktree] = field(default_factory=dict)
    memory: dict[str, object] = field(default_factory=dict)
    result: object = None
    error: Exception | None = None


@pytest.fixture(params=["real", "fake"], autouse=True)
def implementation(request: pytest.FixtureRequest) -> str:
    """Every scenario of this module runs once per implementation (conftest.py drops real_only ones from the fake run)."""
    return str(request.param)


@pytest.fixture
def world(implementation: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    apply_hermetic_env(monkeypatch, identity=_ME, home=tmp_path / "home")
    rig: Rig = RealRig(tmp_path, monkeypatch) if implementation == "real" else FakeRig(tmp_path)
    return World(rig, implementation, monkeypatch)


def _text(raw: str) -> str:
    return raw.replace("\\n", "\n")


def _files(spec: str) -> list[tuple[str, str]]:
    """``a.txt="x", "my file.txt"="y"`` as (path, text) pairs."""
    return [(rel.strip('"'), _text(text)) for rel, text in _FILE.findall(spec)]


def _expand(world: World, raw: str) -> str:
    def value(match: re.Match[str]) -> str:
        kind, arg = match.group(1), match.group(2) or ""
        if kind == "root":
            return str(world.rig.root)
        if kind == "head":
            return world.rig.head(world.wts[arg])
        if kind == "mem":
            return str(world.memory[arg])
        if kind == "blob":
            data = _text(arg).encode()
            return hashlib.sha1(f"blob {len(data)}".encode() + b"\0" + data, usedforsecurity=False).hexdigest()[:7]
        return match.group(0)

    return _PLACEHOLDER.sub(value, raw)


def _plain(item: object) -> object:
    if isinstance(item, Change):
        return f"{item.path} {item.kind} +{item.added} -{item.deleted}"
    if dataclasses.is_dataclass(item) and not isinstance(item, type):
        return {f.name: _plain(getattr(item, f.name)) for f in dataclasses.fields(item)}
    if isinstance(item, (frozenset, set)):
        return sorted(_plain(i) for i in item)  # type: ignore[type-var]
    if isinstance(item, (list, tuple)):
        return [_plain(i) for i in item]
    return str(item) if hasattr(item, "parts") else item


def _call(world: World, name: str, call: str) -> object:
    node = ast.parse(_expand(world, call), mode="eval").body
    assert isinstance(node, ast.Call)
    assert isinstance(node.func, ast.Name)
    args = [ast.literal_eval(a) for a in node.args]
    kwargs = {k.arg: ast.literal_eval(k.value) for k in node.keywords if k.arg}
    if node.func.id in _PATH_ARGS:
        args[0] = Path(args[0])
    wt = world.wts[name]
    target = wt if hasattr(wt, node.func.id) else wt.repo
    return getattr(target, node.func.id)(*args, **kwargs)


def _dig(value: object, path: str) -> object:
    for part in path.split("."):
        value = value[int(part)] if part.isdigit() else getattr(value, part)  # type: ignore[index]
    return value


# -- arranging -----------------------------------------------------------------------------------------
@given(parsers.parse('a repository "{name}"'))
def _repository(world: World, name: str) -> None:
    world.wts[name] = world.rig.init(name)


@given(parsers.parse('an origin "{name}"'))
def _origin(world: World, name: str) -> None:
    world.memory[f"origin:{name}"] = world.rig.make_origin(name)


@given(parsers.parse('the origin "{name}" holds {files}'))
def _origin_holds(world: World, name: str, files: str) -> None:
    _advance(world, name, "main", files)


@given(parsers.parse('the origin "{name}" advances "{branch}" with {files}'))
@when(parsers.parse('the origin "{name}" advances "{branch}" with {files}'))
def _advance(world: World, name: str, branch: str, files: str) -> None:
    world.rig.advance_origin(str(world.memory[f"origin:{name}"]), branch, dict(_files(files)))


@given(parsers.parse('the origin "{name}" is offline'))
@when(parsers.parse('the origin "{name}" goes offline'))
def _offline(world: World, name: str) -> None:
    world.rig.origin_offline(str(world.memory[f"origin:{name}"]), offline=True)


@given(parsers.parse('"{name}" has the origin "{origin}" as remote "{remote}"'))
def _add_remote(world: World, name: str, origin: str, remote: str) -> None:
    world.rig.add_remote(world.wts[name], remote, str(world.memory[f"origin:{origin}"]))


@given(parsers.parse('"{name}" is a clone of the origin "{origin}"'))
def _clone(world: World, name: str, origin: str) -> None:
    world.wts[name] = world.rig.clone(str(world.memory[f"origin:{origin}"]), name)


@given(parsers.parse('a folder "{name}"'))
def _folder(world: World, name: str) -> None:
    world.rig.plain_folder(name)


@given(parsers.parse('"{name}" is the plain folder'))
def _plain_folder(world: World, name: str) -> None:
    folder = world.rig.plain_folder(name)
    anchor = world.rig.init(f"{name}-anchor")
    world.wts[name] = anchor.repo.worktree(folder)


@given(parsers.parse('"{name}" is the folder "{sub}" inside "{parent}"'))
def _sub_folder(world: World, name: str, sub: str, parent: str) -> None:
    folder = world.rig.sub_folder(world.wts[parent], sub)
    world.wts[name] = world.wts[parent].repo.worktree(folder)


@given(parsers.parse('"{name}" config "{key}" is "{value}"'))
@when(parsers.parse('"{name}" config "{key}" becomes "{value}"'))
def _config(world: World, name: str, key: str, value: str) -> None:
    world.rig.set_config(world.wts[name], key, _expand(world, value))


@given(parsers.parse('"{name}" has a {kind} hook that {mode}'))
def _hook(world: World, name: str, kind: str, mode: str) -> None:
    world.rig.hook(world.wts[name], kind, mode)


@given(parsers.parse('"{name}" holds an index lock'))
def _index_lock(world: World, name: str) -> None:
    world.rig.lock_index(world.wts[name])


@given(parsers.parse('the signer of "{name}" fails'))
def _signer_fails(world: World, name: str) -> None:
    repo = world.wts[name].repo
    if isinstance(repo, FakeRepo):
        repo.hooks.commit_failure = "error: gpg failed to sign the data"
        return
    assert isinstance(repo, RealRepo)
    original = repo.run

    def signing_process(
        cwd: Path,
        *args: str,
        check: bool = True,
        pin: bool = True,
        stdin: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> Done:
        config = ("-c", "commit.gpgsign=true", "-c", "gpg.program=false") if "commit" in args else ()
        return original(cwd, *config, *args, check=check, pin=pin, stdin=stdin, env=env, timeout=timeout)

    world.monkeypatch.setattr(repo, "run", signing_process)


@then("the push succeeded")
def _push_succeeded(world: World) -> None:
    if isinstance(world.result, CommandResult):
        assert world.result.ok, world.result.output
    else:
        assert type(world.result).__name__ == "Pushed", world.result


@given(parsers.parse('"{name}" commits "{message}" with {files}'))
@when(parsers.parse('"{name}" commits "{message}" with {files}'))
def _commit_with(world: World, name: str, message: str, files: str) -> None:
    wt = world.wts[name]
    for rel, text in _files(files):
        world.rig.write(wt, rel, text)
    assert type(wt.record(_text(message), paths="all")).__name__ == "Recorded"


@given(parsers.parse('"{name}" writes {files}'))
@when(parsers.parse('"{name}" writes {files}'))
def _writes(world: World, name: str, files: str) -> None:
    for rel, text in _files(files):
        world.rig.write(world.wts[name], rel, text)


@given(parsers.re(r'"(?P<name>\w+)" stages (?P<paths>\[.*\])'))
@when(parsers.re(r'"(?P<name>\w+)" stages (?P<paths>\[.*\])'))
def _stages(world: World, name: str, paths: str) -> None:
    wt = world.wts[name]
    picks = ast.literal_eval(paths)
    if isinstance(wt, FakeWorktree):
        stage(wt.repo._state, wt.state(), picks)
    else:
        run(wt.path, "--literal-pathspecs", "add", "-A", "--", *picks)


@then(parsers.parse('the index of "{name}" reads "{rel}" as "{text}"'))
def _index_reads(world: World, name: str, rel: str, text: str) -> None:
    wt = world.wts[name]
    got = wt.repo._state.store.blobs[wt.state().index[rel]].decode() if isinstance(wt, FakeWorktree) else run(wt.path, "show", f":{rel}")
    assert got == _text(text)


@then("the failure cannot be retried")
def _not_retryable(world: World) -> None:
    assert isinstance(world.error, GitUnavailable)
    assert not world.error.retryable


@when(parsers.parse('"{name}" edits "{rel}" to "{text}" within the same clock tick'))
def _same_tick(world: World, name: str, rel: str, text: str) -> None:
    world.rig.edit_same_tick(world.wts[name], rel, _text(text))


@given(parsers.parse('"{name}" removes "{rel}"'))
@when(parsers.parse('"{name}" removes "{rel}"'))
def _removes(world: World, name: str, rel: str) -> None:
    world.rig.remove(world.wts[name], rel)


@given(parsers.parse('"{name}" remembers its head as "{label}"'))
@when(parsers.parse('"{name}" remembers its head as "{label}"'))
def _remember_head(world: World, name: str, label: str) -> None:
    world.memory[label] = world.rig.head(world.wts[name])


@given(parsers.parse('"{name}" stages a rename from "{old}" to "{new}"'))
def _stage_rename(world: World, name: str, old: str, new: str) -> None:
    wt = world.wts[name]
    if isinstance(wt, FakeWorktree):
        state = wt.state()
        state.files[new] = state.files.pop(old)
        state.index[new] = state.index.pop(old)
    else:
        run(wt.path, "mv", "--", old, new)


@given(parsers.re(r'"(?P<name>\w+)" remembers (?P<expr>\w+\(.*\)\.[\w.]+) as "(?P<label>[^"]+)"'))
@when(parsers.re(r'"(?P<name>\w+)" remembers (?P<expr>\w+\(.*\)\.[\w.]+) as "(?P<label>[^"]+)"'))
def _remember(world: World, name: str, expr: str, label: str) -> None:
    call, _, attr = expr.rpartition(").")
    value = _call(world, name, call + ")")
    world.memory[label] = _plain(_dig(value, attr))


@given(parsers.parse('"{name}" calls {call}'))
@when(parsers.parse('"{name}" calls {call}'))
def _calls(world: World, name: str, call: str) -> None:
    world.result = _call(world, name, call)


@given(parsers.parse('"{name}" adds a worktree "{rel}" at "{rev}" as "{label}"'))
@when(parsers.parse('"{name}" adds a worktree "{rel}" at "{rev}" as "{label}"'))
def _worktree(world: World, name: str, rel: str, rev: str, label: str) -> None:
    path = _text(rel).replace("\\t", "\t").replace('\\"', '"')
    world.wts[label] = world.wts[name].repo.add_worktree(world.rig.root / path, _expand(world, rev))


@when(parsers.parse('"{name}" tries {call}'))
def _tries(world: World, name: str, call: str) -> None:
    try:
        world.result = _call(world, name, call)
    except Exception as exc:  # noqa: BLE001 - the scenario names the type it expects
        world.error = exc


@given(parsers.parse('the folder of "{name}" is deleted behind git\'s back'))
@when(parsers.parse('the folder of "{name}" is deleted behind git\'s back'))
def _drop(world: World, name: str) -> None:
    world.rig.drop_checkout(world.wts[name])


@given(parsers.parse('the repositories commit as "{who}"'))
def _identity(world: World, who: str) -> None:
    world.rig.identity = Identity(who, "injected@example.invalid")


@given("the machine has no git identity")
def _no_identity(world: World, tmp_path: Path) -> None:
    apply_hermetic_env(world.monkeypatch, identity=None, config={**QUIET, "user.useConfigOnly": "true"}, home=tmp_path / "home")


@when("git is not on the PATH")
def _no_git(world: World) -> None:
    world.monkeypatch.setenv("PATH", "")


@given(parsers.parse('a competing fetch holds the lock on "{ref}" until the first retry'))
def _ref_lock(world: World, ref: str) -> None:
    rig = world.rig
    assert isinstance(rig, RealRig)
    lock = next(iter(world.wts.values())).path / ".git" / "refs" / "remotes" / f"{ref}.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("", encoding="utf-8")
    rig.locks.append(lock)


# -- checking ------------------------------------------------------------------------------------------
@given(parsers.parse('the observations of "{name}" will fail'))
def _observations_fail(world: World, name: str) -> None:
    wt = world.wts[name]

    def failed_anchor() -> object:
        msg = "unknown observation failure"
        raise GitUnavailable(msg)

    if isinstance(wt, FakeWorktree):
        world.monkeypatch.setattr(wt, "state", failed_anchor)
        world.monkeypatch.setattr(wt.repo, "_anchor", failed_anchor)
        return
    repo = wt.repo
    assert isinstance(repo, RealRepo)

    def failed_process(
        cwd: Path,
        *args: str,
        check: bool = True,
        pin: bool = True,
        stdin: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> Done:
        msg = "unknown observation failure"
        raise GitUnavailable(msg)

    world.monkeypatch.setattr(repo, "run", failed_process)


@given(parsers.parse('the LFS command of "{name}" will {outcome}'))
@given(parsers.parse('the LFS command of "{name}" cannot {outcome}'))
def _lfs_outcome(world: World, name: str, outcome: str) -> None:
    repo = world.wts[name].repo
    if isinstance(repo, FakeRepo):
        repo.hooks.lfs_available = True
        repo.hooks.lfs_push_failure = "git lfs timed out after 60 min" if outcome == "time out" else None
        repo.hooks.lfs_spawn_failure = "failed to invoke git" if outcome == "start" else None
        return
    assert isinstance(repo, RealRepo)
    original = repo.run

    def lfs_process(
        cwd: Path,
        *args: str,
        check: bool = True,
        pin: bool = True,
        stdin: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> Done:
        if args[:2] == ("lfs", "push"):
            if outcome == "time out":
                msg = "git lfs timed out after 3600s"
                raise GitTimeout(msg)
            if outcome == "start":
                msg = "failed to invoke git"
                raise GitUnavailable(msg)
            return Done(0, b"", "")
        return original(cwd, *args, check=check, pin=pin, stdin=stdin, env=env, timeout=timeout)

    world.monkeypatch.setattr(repo, "run", lfs_process)


@given(parsers.parse('the origin "{name}" refuses non fast forward pushes'))
def _remote_policy(world: World, name: str) -> None:
    url = str(world.memory[f"origin:{name}"])
    if isinstance(world.rig, FakeRig):
        world.rig._origins[url].state.config["receive.denynonfastforwards"] = "true"
    else:
        run(Path(url), "config", "receive.denyNonFastForwards", "true")


@given(parsers.parse('the squash commit of "{name}" will fail'))
def _squash_fails(world: World, name: str) -> None:
    repo = world.wts[name].repo
    if isinstance(repo, FakeRepo):
        repo.hooks.squash_failure = "squash failed"
        return
    assert isinstance(repo, RealRepo)
    original = repo.run

    def fail_commit(
        cwd: Path,
        *args: str,
        check: bool = True,
        pin: bool = True,
        stdin: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> Done:
        if "commit" in args:
            return Done(1, b"", "squash failed")
        return original(cwd, *args, check=check, pin=pin, stdin=stdin, env=env, timeout=timeout)

    world.monkeypatch.setattr(repo, "run", fail_commit)


@then(parsers.parse('the squash policy outcome is "{outcome}"'))
def _squash_outcome(world: World, outcome: str) -> None:
    wt = world.wts["r"]
    if outcome == "raised":
        assert isinstance(world.error, GitUnavailable)
        assert world.rig.head(wt) == world.memory["before"]
    else:
        assert world.error is None
        assert type(world.result).__name__ == "Rebased"
        assert isinstance(world.result, Rebased)
        assert world.result.squash_failure == "squash failed"
        assert world.result.squashed is False
        assert [row.subject for row in wt.repo.history(["HEAD"], limit=2)] == ["second", "first"]


@then(parsers.parse('the branch "{branch}" of "{name}" rewritten is {expected}'))
def _branch_rewritten(world: World, branch: str, name: str, expected: str) -> None:
    sha = world.wts[name].repo.history([branch], limit=1)[0].sha
    assert (sha != world.memory[branch]) == ast.literal_eval(expected)


@then(parsers.parse('the command output contains "{text}"'))
def _command_output(world: World, text: str) -> None:
    assert isinstance(world.result, CommandResult)
    assert text in world.result.output


@then(parsers.parse('the refusal reason is "{reason}"'))
def _refusal_reason(world: World, reason: str) -> None:
    assert isinstance(world.error, WorktreeRemoveRefused)
    expanded = _expand(world, reason)
    assert world.error.reason == expanded
    assert str(world.error) == f"git worktree remove exited 128: {expanded}"


@then(parsers.parse("the status bytes list tracked {tracked} and untracked {untracked}"))
def _status_bytes(world: World, tracked: str, untracked: str) -> None:
    assert isinstance(world.result, bytes)
    assert world.result.endswith(b"\0")
    state = parse_status(world.result.decode("utf-8", "surrogateescape"))
    assert list(state.tracked) == ast.literal_eval(tracked)
    assert list(state.untracked) == ast.literal_eval(untracked)


@then(parsers.parse("the status records with object ids normalized are {expected}"))
def _status_records(world: World, expected: str) -> None:
    assert isinstance(world.result, bytes)
    assert world.result.endswith(b"\0")
    records = world.result.split(b"\0")
    assert records[0].startswith(b"# branch.oid ")
    assert records[1].startswith(b"# branch.head ")
    # Preserve every field and NUL separator; only object identities are outside
    # this structural contract because the fake does not retain conflict stages.
    normalized = re.sub(rb"\b[0-9a-f]{40}\b", b"<oid>", b"\0".join(records[2:]))
    assert normalized == ast.literal_eval(expected)


@then(parsers.re(r"the result is a (?P<kind>[A-Z]\w*)"))
def _result_kind(world: World, kind: str) -> None:
    assert type(world.result).__name__ == kind, world.result


@then(parsers.re(r"the result is (?!a [A-Z]\w*$)(?P<expected>.+)"))
def _result_is(world: World, expected: str) -> None:
    assert _plain(world.result) == ast.literal_eval(_expand(world, expected))


@then(parsers.re(r"the result's (?P<path>[\w.]+) equals its (?P<other>[\w.]+)"))
def _result_equals(world: World, path: str, other: str) -> None:
    assert _plain(_dig(world.result, path)) == _plain(_dig(world.result, other))


@then(parsers.re(r"the (?P<field>\w+) of each result entry is (?P<expected>.+)"))
def _each_entry(world: World, field: str, expected: str) -> None:
    assert isinstance(world.result, (tuple, list))
    assert [_plain(_dig(entry, field)) for entry in world.result] == ast.literal_eval(_expand(world, expected))


@then(parsers.re(r"the (?P<ordinal>first|second) item of each result entry is (?P<expected>.+)"))
def _each_item(world: World, ordinal: str, expected: str) -> None:
    assert isinstance(world.result, (tuple, list))
    index = {"first": 0, "second": 1}[ordinal]
    assert [_plain(entry[index]) for entry in world.result] == ast.literal_eval(_expand(world, expected))


@then(parsers.re(r"the tree lists (?P<expected>\[.*\])"))
def _tree_lists(world: World, expected: str) -> None:
    assert sorted(world.result.files) == ast.literal_eval(expected)  # type: ignore[attr-defined]


@then(parsers.re(r'the tree reads "(?P<rel>[^"]+)" as (?P<expected>.+)'))
def _tree_reads(world: World, rel: str, expected: str) -> None:
    got = world.result.read(rel)  # type: ignore[attr-defined]
    assert got == (None if expected == "nothing" else _text(ast.literal_eval(expected)).encode())


@then(parsers.parse("the result has {count:d} entries"))
def _count(world: World, count: int) -> None:
    assert isinstance(world.result, (tuple, list))
    assert len(world.result) == count


@then(parsers.re(r"the result's (?P<path>[\w.]+) (?:is|are) (?!not )(?P<expected>.+)"))
def _result_attr(world: World, path: str, expected: str) -> None:
    assert _plain(_dig(world.result, path)) == ast.literal_eval(_expand(world, expected))


@then(parsers.re(r"the result's (?P<path>[\w.]+) is not (?P<expected>.+)"))
def _result_attr_not(world: World, path: str, expected: str) -> None:
    assert _plain(_dig(world.result, path)) != ast.literal_eval(_expand(world, expected))


@then("the result looks like a sha")
def _result_sha(world: World) -> None:
    assert isinstance(world.result, str)
    assert re.fullmatch(r"[0-9a-f]{40}", world.result)


@then(parsers.parse('the file "{rel}" of "{name}" holds "{text}"'))
def _file_holds(world: World, name: str, rel: str, text: str) -> None:
    assert world.rig.read(world.wts[name], rel) == _text(text)


@then(parsers.parse('the file "{rel}" of "{name}" is absent'))
def _file_absent(world: World, name: str, rel: str) -> None:
    assert world.rig.read(world.wts[name], rel) is None


@then(parsers.parse('the file "{rel}" of "{name}" has conflict markers'))
def _file_markers(world: World, name: str, rel: str) -> None:
    content = world.rig.read(world.wts[name], rel) or ""
    assert "<<<<<<<" in content
    assert "=======" in content
    assert ">>>>>>>" in content


@then(parsers.parse("the call raises {kind}"))
def _raises(world: World, kind: str) -> None:
    assert world.error is not None, f"nothing was raised; the result was {world.result!r}"
    assert type(world.error).__name__ == kind, repr(world.error)


@then("the failure may be retried")
def _retryable(world: World) -> None:
    assert isinstance(world.error, GitUnavailable)
    assert world.error.retryable


@then(parsers.parse('the failure hint is "{hint}"'))
def _hint(world: World, hint: str) -> None:
    assert isinstance(world.error, GitUnavailable)
    assert world.error.hint == hint


@then(parsers.parse('the author of the last commit of "{name}" is "{who}"'))
def _author(world: World, name: str, who: str) -> None:
    assert run(world.wts[name].path, "log", "-1", "--format=%an").strip() == who


@then(parsers.parse("the fetch rested {count:d} time"))
def _rested(world: World, count: int) -> None:
    rig = world.rig
    assert isinstance(rig, RealRig)
    assert len(rig.rests) == count
