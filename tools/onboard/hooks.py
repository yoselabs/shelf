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

from .operations import Outcome, Result

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
    "any-gate-python": "any-gate-python-v0.1.1",
    "blueprint": "blueprint-v0.2.0",
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


def release_tag(name: str) -> str:
    """The tag a consumer pins `name` to: the gate packages' own, else the tag of the version the shelf holds now (`<name>-v<version>`)."""
    if name in GATE_PACKAGES:
        return GATE_PACKAGES[name]
    manifest = _SHELF_ROOT / "packages" / name / "pyproject.toml"
    return f"{name}-v{tomllib.loads(manifest.read_text())['project']['version']}"


def package_spec(name: str) -> str:
    return f'{{ git = "{_REPO}", subdirectory = "packages/{name}", tag = "{release_tag(name)}" }}'


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


def _ensure_dependency(text: str, name: str) -> str:
    """`text` with `name` a dev dependency sourced by its git tag; unchanged when it already is."""
    data = tomllib.loads(text)
    group = [d for d in data.get("dependency-groups", {}).get("dev", []) if isinstance(d, str)]
    wired = any(d.split("[")[0].split(">")[0].split("=")[0].strip() == name for d in group)
    sourced = name in data.get("tool", {}).get("uv", {}).get("sources", {})
    if not wired:
        if "dependency-groups" not in data:
            text = text.rstrip("\n") + f'\n\n[dependency-groups]\ndev = ["{name}"]\n'
        elif "dev" not in data["dependency-groups"]:
            text = text.replace("[dependency-groups]\n", f'[dependency-groups]\ndev = ["{name}"]\n', 1)
        else:
            text = _into_dev_group(text, name)
    if not sourced:
        if "[tool.uv.sources]" in text:
            text = text.replace("[tool.uv.sources]\n", f"[tool.uv.sources]\n{name} = {package_spec(name)}\n", 1)
        else:
            text = text.rstrip("\n") + f"\n\n[tool.uv.sources]\n{name} = {package_spec(name)}\n"
    return text


def _ensure_source(text: str, name: str) -> str:
    """`text` with a git-tag source for `name` (a transitive shelf dependency); unchanged when the repo already sources it."""
    if name in tomllib.loads(text).get("tool", {}).get("uv", {}).get("sources", {}):
        return text
    if "[tool.uv.sources]" in text:
        return text.replace("[tool.uv.sources]\n", f"[tool.uv.sources]\n{name} = {package_spec(name)}\n", 1)
    return text.rstrip("\n") + f"\n\n[tool.uv.sources]\n{name} = {package_spec(name)}\n"


def ensure_gate_dependency(repo: Path) -> bool:
    """Make the gate's shelf packages (`any-gate`, `blueprint`) dev dependencies of a python+uv repo, pinned by git tag.

    Their own shelf dependencies get a tag source too: uv does not carry a git source to the packages that need it.

    True when pyproject.toml changed. The hook entries and the `check`, `test`, `guard`, `preset` and `blueprint` recipes run them.
    """
    pyproject = repo / "pyproject.toml"
    if not pyproject.is_file():
        return False
    before = pyproject.read_text()
    text = before
    for name in GATE_PACKAGES:
        text = _ensure_dependency(text, name)
        for dep in shelf_closure(name):
            text = _ensure_source(text, dep)
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
            config.write_text(config_text(beads=self.beads, python=(self.repo / "pyproject.toml").exists()))
            ensure_gate_dependency(self.repo)
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
