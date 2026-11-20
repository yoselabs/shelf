"""The `hooks` operation: prek owns the git hooks, configured from the blueprint recipe.

Replaces the hand-written hook installer (tools/hooks/install.py, deleted 2026-10-11). The recipe
(docs/research/blueprint-skill/research/hooks-and-beads.md): bd never installs hooks itself; its
five events run from `.pre-commit-config.yaml`, first, then the shelf's commit guard and ruff on staged
files, then `just check`. A failing check blocks the commit and bd still runs; bd's own injection into
another manager's hook file made a failing check stop blocking.

Append-only like the rest of onboarding: an existing `.pre-commit-config.yaml` is kept as the owner
wrote it, and the result says so; blueprint's `gate.hooks-recipe` then judges it.

Effect-assertion: after `prek install`, the installed pre-commit hook must be prek's, `core.hooksPath`
must be unset, and no bd block may be injected in the hooks folder.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .operations import Outcome, Result

if TYPE_CHECKING:
    from collections.abc import Callable

_SHELF_ROOT = Path(__file__).resolve().parent.parent.parent
_RECIPE = _SHELF_ROOT / "packages" / "blueprint" / "src" / "blueprint" / "recipes" / "pre-commit-config.yaml"
_CONFIG = ".pre-commit-config.yaml"
_BEADS_MARKER = "BEGIN BEADS INTEGRATION"
_GATE_BLOCK = "- repo: local\n  hooks:\n  - id: gate\n"

# The shelf consumer's own fast checks, between bd's entries and the gate. The guard is `blueprint guard`, a dev dependency,
# so a consumer needs no shelf clone.
_SHELF_HOOKS = """# The shelf's commit guard and ruff on staged files (shelf onboarding).
- repo: local
  hooks:
  - id: shelf-guard
    name: no local shelf source
    entry: uv run blueprint guard
    language: system
    always_run: true
    pass_filenames: false
    stages: [pre-commit]
  - id: ruff-check
    name: ruff check
    entry: uv run --frozen ruff check --force-exclude
    language: system
    types: [python]
    stages: [pre-commit]
  - id: ruff-format
    name: ruff format
    entry: uv run --frozen ruff format --check --force-exclude
    language: system
    types: [python]
    stages: [pre-commit]
"""


def config_text(*, beads: bool, python: bool) -> str:
    """The `.pre-commit-config.yaml` onboarding writes: the recipe, the shelf's hooks before the gate."""
    recipe = _RECIPE.read_text()
    head, gate = recipe.split(_GATE_BLOCK, 1)
    if not beads:
        head = head[: head.index("repos:")] + "repos:\n"
    shelf = _SHELF_HOOKS if python else ""  # the guard and ruff are python tools: a repo with none gets neither
    if not python:  # any-gate is a python package: a repo with none runs the gate plainly, with no skip of a tree that passed
        gate = gate.replace(_GATE_ENTRY, "just check")
    return head + shelf + _GATE_BLOCK + gate


_REPO = "https://github.com/yoselabs/shelf"
# The shelf packages a consumer's gate runs, pinned by git tag: `any-gate` (tree record, pre-push skip, test runner), `any-gate-python`
# (the pytest planner and runner `blueprint test` calls) and `blueprint` (the `guard`, `preset`, `render`, `test` and `check` steps).
# A consumer needs no shelf clone.
GATE_PACKAGES = {
    "any-gate": "any-gate-v0.1.1",
    "any-gate-python": "any-gate-python-v0.1.2",
    "blueprint": "blueprint-v0.4.0",
}


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _shelf_requirements(name: str) -> set[str]:
    """The shelf packages `name` requires, directly."""
    manifest = _SHELF_ROOT / "packages" / name / "pyproject.toml"
    reqs = tomllib.loads(manifest.read_text()).get("project", {}).get("dependencies", [])
    found = {_norm(m.group(1)) for r in reqs if (m := re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", r))}
    return {n for n in found if (_SHELF_ROOT / "packages" / n / "pyproject.toml").is_file()}


def shelf_closure(name: str) -> list[str]:
    """Every shelf package `name` needs at runtime, itself excluded. A git source is not transitive in uv: the consumer lists each."""
    seen: set[str] = set()
    queue = [name]
    while queue:
        for dep in _shelf_requirements(queue.pop()) - seen:
            seen.add(dep)
            queue.append(dep)
    return sorted(seen - {name})


def _workspace_sources(name: str) -> set[str]:
    """The packages `name`'s manifest sources as `{ workspace = true }`."""
    manifest = _SHELF_ROOT / "packages" / name / "pyproject.toml"
    sources = tomllib.loads(manifest.read_text()).get("tool", {}).get("uv", {}).get("sources", {})
    return {_norm(k) for k, v in sources.items() if isinstance(v, dict) and v.get("workspace") is True}


def _tag_owner(name: str) -> str | None:
    """The gate package that fixes `name`'s tag, or None.

    A gate package that needs another gate package (`any-gate-python` needs `any-gate`) sources its workspace siblings as
    `{ workspace = true }`, which uv resolves to the git URL at that package's own tag. A consumer pinning one of them at any other
    tag fails to lock with conflicting URLs, so those siblings share the owner's tag.
    """
    for owner in GATE_PACKAGES:
        if (GATE_PACKAGES.keys() - {owner}) & set(_shelf_requirements(owner)) and name in _workspace_sources(owner):
            return owner
    return None


def release_tag(name: str) -> str:
    """The tag a consumer pins `name` to: its tag owner's, else the gate packages' own, else the tag of the version the shelf holds now."""
    if (owner := _tag_owner(name)) is not None:
        return GATE_PACKAGES[owner]
    if name in GATE_PACKAGES:
        return GATE_PACKAGES[name]
    manifest = _SHELF_ROOT / "packages" / name / "pyproject.toml"
    return f"{name}-v{tomllib.loads(manifest.read_text())['project']['version']}"


def package_spec(name: str, url: str = _REPO) -> str:
    return f'{{ git = "{url}", subdirectory = "packages/{name}", tag = "{release_tag(name)}" }}'


# What the gate's test runner asks of the project under test: `any-gate-python` passes `-n` to pytest (its `pytest` extra says so too).
GATE_PLUGINS = ("pytest-xdist",)
GATE_SPEC = package_spec("any-gate")
_GATE_ENTRY = "uv run python -m any_gate pre-push --gate check -- uv run just check"
_DEV_GROUP = re.compile(r"^dev\s*=\s*\[", re.MULTILINE)


def _into_dev_group(text: str, name: str) -> str:
    """`text` with `name` first in the `dev` list of `[dependency-groups]`, whether the list is on one line or several."""
    opened = _DEV_GROUP.search(text)
    if opened is None:
        return text
    rest_of_line = text[opened.end() :].split("\n", 1)[0]
    entry = f'"{name}", ' if "]" in rest_of_line else f'\n    "{name}",'
    return text[: opened.end()] + entry + text[opened.end() :]


class ShelfSourceConflict(Exception):  # noqa: N818 -- a stop, named for what it says
    """A shelf source the repo already has cannot lock with the kit: onboarding stops rather than write a pyproject that cannot lock."""


def _same_repo(url: str) -> bool:
    return url.strip().rstrip("/").removesuffix(".git").lower() == _REPO.lower()


def _shelf_sources(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The repo's git sources that point at the shelf (whatever the URL spelling), by package name."""
    sources = data.get("tool", {}).get("uv", {}).get("sources", {})
    return {_norm(n): s for n, s in sources.items() if isinstance(s, dict) and isinstance(s.get("git"), str) and _same_repo(s["git"])}


def _spelling(data: dict[str, Any]) -> str:
    """The shelf URL as the repo already spells it: a second spelling is a second source for uv, which needs an override to lock."""
    return next((s["git"] for s in _shelf_sources(data).values()), _REPO)


def _version(tag: str, name: str) -> tuple[int, ...] | None:
    m = re.fullmatch(rf"{re.escape(name)}-v(\d+(?:\.\d+)*)", tag)
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


_CLAUSE = re.compile(r"(>=|<=|==|>|<)\s*(\d+(?:\.\d+)*)")
_OPS: dict[str, Callable[[tuple[int, ...], tuple[int, ...]], bool]] = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
}


def _satisfies(version: tuple[int, ...], spec: str) -> bool:
    width = max(len(version), 3)

    def pad(v: tuple[int, ...]) -> tuple[int, ...]:
        return (*v, *([0] * (width - len(v))))

    return all(_OPS[op](pad(version), pad(tuple(int(x) for x in num.split(".")))) for op, num in _CLAUSE.findall(spec))


def _kit_requirements() -> list[tuple[str, str, str]]:
    """`(kit package, shelf package, specifier)` for every shelf dependency of the gate packages and their closure."""
    found = []
    for kit in [*GATE_PACKAGES, *(d for g in GATE_PACKAGES for d in shelf_closure(g))]:
        manifest = _SHELF_ROOT / "packages" / kit / "pyproject.toml"
        reqs = tomllib.loads(manifest.read_text()).get("project", {}).get("dependencies", [])
        matches = (re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(.*)", req) for req in reqs)
        found.extend((kit, _norm(m.group(1)), m.group(2)) for m in matches if m and _norm(m.group(1)) in _all_shelf())
    return found


def _all_shelf() -> set[str]:
    return {p.parent.name for p in (_SHELF_ROOT / "packages").glob("*/pyproject.toml")}


def check_shelf_sources(text: str) -> None:
    """Raise `ShelfSourceConflict` when a shelf source `text` already holds does not satisfy what a kit package requires."""
    existing = _shelf_sources(tomllib.loads(text))
    clashes = []
    for kit, dep, spec in _kit_requirements():
        tag = existing.get(dep, {}).get("tag", "")
        version = _version(str(tag), dep) if tag else None
        if version is not None and not _satisfies(version, spec):
            clashes.append(f"{dep} is pinned to {tag}, but {kit} needs {dep}{spec}")
    if not clashes:
        return
    pins = ", ".join(f"{n} ({s.get('tag', s.get('rev', 'no tag'))})" for n, s in sorted(existing.items()))
    msg = (
        "shelf sources that cannot lock with the gate kit: "
        + "; ".join(sorted(set(clashes)))
        + f". Shelf sources in this repo: {pins}. They come from one shelf snapshot and must move together: "
        "upgrade all of them to one current snapshot (a shelf snapshot upgrade, its own change), "
        "then re-run onboarding. Nothing was written."
    )
    raise ShelfSourceConflict(msg)


def _ensure_dependency(text: str, name: str, *, tagged: bool = True) -> str:
    """`text` with `name` a dev dependency (sourced by its git tag unless `tagged` is off); unchanged when it already is."""
    data = tomllib.loads(text)
    group = [d for d in data.get("dependency-groups", {}).get("dev", []) if isinstance(d, str)]
    wired = any(d.split("[")[0].split(">")[0].split("=")[0].strip() == name for d in group)
    sourced = name in data.get("tool", {}).get("uv", {}).get("sources", {})
    url = _spelling(data)
    if not wired:
        if "dependency-groups" not in data:
            text = text.rstrip("\n") + f'\n\n[dependency-groups]\ndev = ["{name}"]\n'
        elif "dev" not in data["dependency-groups"]:
            text = text.replace("[dependency-groups]\n", f'[dependency-groups]\ndev = ["{name}"]\n', 1)
        else:
            text = _into_dev_group(text, name)
    if tagged and not sourced:
        if "[tool.uv.sources]" in text:
            text = text.replace("[tool.uv.sources]\n", f"[tool.uv.sources]\n{name} = {package_spec(name, url)}\n", 1)
        else:
            text = text.rstrip("\n") + f"\n\n[tool.uv.sources]\n{name} = {package_spec(name, url)}\n"
    return text


def _ensure_source(text: str, name: str) -> str:
    """`text` with a git-tag source for `name` (a transitive shelf dependency); unchanged when the repo already sources it."""
    data = tomllib.loads(text)
    if name in data.get("tool", {}).get("uv", {}).get("sources", {}):
        return text
    spec = package_spec(name, _spelling(data))
    if "[tool.uv.sources]" in text:
        return text.replace("[tool.uv.sources]\n", f"[tool.uv.sources]\n{name} = {spec}\n", 1)
    return text.rstrip("\n") + f"\n\n[tool.uv.sources]\n{name} = {spec}\n"


def ensure_gate_dependency(repo: Path) -> bool:
    """Make the gate's shelf packages (`any-gate`, `blueprint`) dev dependencies of a python+uv repo, pinned by git tag.

    Their own shelf dependencies get a tag source too: uv does not carry a git source to the packages that need it.

    Raises `ShelfSourceConflict` (writing nothing) when a shelf source the repo already has cannot lock with them.

    True when pyproject.toml changed. The hook entries and the `check`, `test`, `guard`, `preset` and `blueprint` recipes run them.
    """
    pyproject = repo / "pyproject.toml"
    if not pyproject.is_file():
        return False
    before = pyproject.read_text()
    check_shelf_sources(before)
    text = before
    for name in GATE_PACKAGES:
        text = _ensure_dependency(text, name)
        for dep in shelf_closure(name):
            text = _ensure_source(text, dep)
    for plugin in GATE_PLUGINS:
        text = _ensure_dependency(text, plugin, tagged=False)
    if text == before:
        return False
    tomllib.loads(text)  # never leave a pyproject that does not parse
    pyproject.write_text(text)
    return True


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)


def _prek(repo: Path) -> list[str] | None:
    local = repo / ".venv" / "bin" / "prek"
    if local.is_file():
        return [str(local)]
    if shutil.which("prek"):
        return ["prek"]
    if shutil.which("uvx"):
        return ["uvx", "prek"]
    return None


# Hook files onboarding may replace: prek's own, bd's injected ones, and the old shelf installer's.
_REPLACEABLE = ("File generated by prek", "File generated by pre-commit", _BEADS_MARKER, "shelf-guard", "shelf-lint")


def _foreign_hook(repo: Path) -> str | None:
    """The installed pre-commit hook, when another manager (husky, lefthook, a hand-written script) owns it."""
    pre_commit = _hooks_dir(repo) / "pre-commit"
    if not pre_commit.is_file():
        return None
    text = pre_commit.read_text(errors="replace")
    return None if any(marker in text for marker in _REPLACEABLE) else str(pre_commit)


def _hooks_dir(repo: Path) -> Path:
    path = Path(_git(repo, "rev-parse", "--git-path", "hooks").stdout.strip() or ".git/hooks")
    return path if path.is_absolute() else repo / path


@dataclass
class HooksOperation:
    """Writes the prek config (if absent), clears bd's own hooks and any hooksPath, runs `prek install`."""

    repo: Path
    beads: bool = True
    name: str = "hooks"
    requires: tuple[str, ...] = ()

    def run(self, _results: dict[str, Result]) -> Result:
        """Apply the recipe, install, and assert the installed hooks are prek's."""
        if _git(self.repo, "rev-parse", "--git-dir").returncode != 0:
            return Result(Outcome.COULD_NOT_APPLY, verified=False, message=f"{self.repo} is not a git repository")
        prek = _prek(self.repo)
        if prek is None:
            return Result(Outcome.COULD_NOT_APPLY, verified=False, message="prek not found: `uv tool install prek`, then re-run")

        foreign = _foreign_hook(self.repo)
        if foreign:
            return Result(
                Outcome.FAILED,
                verified=False,
                message=f"{foreign}: another hook manager owns it; move its checks into {_CONFIG}, then re-run",
            )
        config = self.repo / _CONFIG
        kept = config.exists()
        if not kept:
            try:
                ensure_gate_dependency(self.repo)
            except ShelfSourceConflict as stop:
                return Result(Outcome.COULD_NOT_APPLY, verified=False, message=str(stop))
            config.write_text(config_text(beads=self.beads, python=(self.repo / "pyproject.toml").exists()))
        if self.beads and shutil.which("bd"):
            subprocess.run(["bd", "hooks", "uninstall"], cwd=self.repo, capture_output=True, text=True, check=False)
        _git(self.repo, "config", "--local", "--unset", "core.hooksPath")
        install = subprocess.run([*prek, "install", "--overwrite"], cwd=self.repo, capture_output=True, text=True, check=False)
        if install.returncode != 0:
            return Result(Outcome.FAILED, verified=False, message=f"prek install failed: {(install.stderr or install.stdout).strip()}")
        return _verify(self.repo, kept=kept)


def _verify(repo: Path, *, kept: bool) -> Result:
    hooks = _hooks_dir(repo)
    pre_commit = hooks / "pre-commit"
    if not pre_commit.is_file() or "File generated by prek" not in pre_commit.read_text(errors="replace"):
        return Result(Outcome.FAILED, verified=False, message=f"{pre_commit} is not prek's after `prek install`")
    injected = sorted(p.name for p in hooks.iterdir() if p.is_file() and _BEADS_MARKER in p.read_text(errors="replace"))
    if injected:
        return Result(Outcome.FAILED, verified=False, message=f"bd's block is still in {', '.join(injected)}")
    if _git(repo, "config", "--local", "core.hooksPath").stdout.strip():
        return Result(Outcome.FAILED, verified=False, message="core.hooksPath is still set")
    done = f"kept the existing {_CONFIG}" if kept else f"wrote {_CONFIG} from the blueprint recipe"
    return Result(Outcome.APPLIED, verified=True, message=f"{done}; prek installed its hooks")


if __name__ == "__main__":  # pragma: no cover - a debugging entry point
    sys.stdout.write(config_text(beads=True, python=True))
