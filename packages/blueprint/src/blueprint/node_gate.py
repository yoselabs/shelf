"""The node stack's gate steps, rendered from the tool configs a folder commits (`blueprint gate render`).

a2kay wrote these by hand for its `ui/` folder: Biome, tsc, knip, dependency-cruiser and vitest, behind one locked install. The tool is the
repo's choice, read from its config file: a folder with no `biome.json` gets no `ui-lint`, one with ESLint is left to its own recipe.
Step names are `ui-<slot>` (`ui-arch` is the node twin of python's `arch`: both are the layering check, over different languages).
One folder gets the set: the first node manifest with a lockfile.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import TYPE_CHECKING

from blueprint.profile import detected_stack_roots

if TYPE_CHECKING:
    from pathlib import Path

# lockfile -> (install command, how a package's binary is run without installing it)
_MANAGERS = {
    "package-lock.json": ("npm ci --no-audit --no-fund", "npx --no-install"),
    "pnpm-lock.yaml": ("pnpm install --frozen-lockfile", "pnpm exec"),
    "yarn.lock": ("yarn install --immutable", "yarn exec"),
}
_HEADER = (
    "# Rendered by `blueprint gate render` -- never edit; a recipe of the same name in the repo's justfile replaces it\n"
    "# only through a declared override (gate.recipe-shadowing).\n"
    "# The node stack: each step runs the tool whose config the folder commits (Biome, tsc, knip, dependency-cruiser,\n"
    "# vitest), after one locked install.\n"
)
INPUT_STEPS = ("ui-lint", "ui-types", "ui-deps", "ui-arch", "ui-test")


@dataclass(frozen=True)
class NodePlan:
    """The node folder's rendered part: the folder, the steps `check` runs, and the part's text."""

    folder: str
    steps: tuple[str, ...]
    text: str


def plan(repo: Path) -> NodePlan | None:
    """The node steps for this repo, or None when no node folder has a lockfile or a configured tool."""
    for stack, folder in sorted(detected_stack_roots(repo)):
        if stack not in {"node", "node-tooling"}:
            continue
        found = next((lock for lock in _MANAGERS if (repo / folder / lock).is_file()), "")
        if not found:
            continue
        chosen = _recipes(repo / folder, folder, *_MANAGERS[found])
        if chosen:
            install = _install(folder, _MANAGERS[found][0])
            text = _HEADER + "\n" + "\n\n".join([install, *(recipe for _, recipe in chosen)]) + "\n"
            return NodePlan(folder, tuple(step for step, _ in chosen), text)
    return None


def inputs_folder(folder: str) -> str:
    """The glob of everything under the folder: `ui/*`, or `*` for a folder at the repo root."""
    return "*" if folder == "." else f"{folder}/*"


def _in(folder: str, command: str) -> str:
    return command if folder == "." else f"cd {shlex.quote(folder)} && {command}"


def _has(root: Path, *names: str) -> bool:
    return any((root / name).is_file() for name in names)


def _package_mentions(root: Path, word: str) -> bool:
    package = root / "package.json"
    return package.is_file() and word in package.read_text()


def _install(folder: str, command: str) -> str:
    lock = f"{folder}/.node-install.lock" if folder != "." else ".node-install.lock"
    modules = f"{folder}/node_modules" if folder != "." else "node_modules"
    return f"""# The node packages, installed once from the frozen lockfile. The gate starts every step at once and each needs them, so a
# fresh clone would run several installs into one folder: the first takes a lock (mkdir is atomic; macOS has no flock) and the rest
# wait for it, then find the packages there. A killed run leaves the lock folder behind: delete {lock}.
[private]
ui-install:
    #!/usr/bin/env bash
    set -euo pipefail
    [ -d {modules} ] && exit 0
    until mkdir {lock} 2>/dev/null; do sleep 1; done
    trap 'rmdir {lock}' EXIT
    [ -d {modules} ] || {_in(folder, command)}"""


def _recipes(root: Path, folder: str, _install_command: str, run: str) -> list[tuple[str, str]]:
    def recipe(name: str, doc: str, command: str) -> tuple[str, str]:
        return name, f"# {doc}\n[group('gate')]\n{name}: ui-install\n    {_in(folder, f'{run} {command}')}"

    out: list[tuple[str, str]] = []
    if _has(root, "biome.json", "biome.jsonc"):
        out.append(recipe("ui-lint", "Biome over the folder (format and lint), warnings failing too.", "biome ci --error-on-warnings ."))
    if _has(root, "tsconfig.json"):
        out.append(recipe("ui-types", "tsc over the folder, nothing emitted.", "tsc --noEmit"))
    if _has(root, "knip.json", "knip.jsonc") or _package_mentions(root, '"knip"'):
        out.append(recipe("ui-deps", "knip: no unused or unlisted dependency, no unused export.", "knip"))
    if _has(root, ".dependency-cruiser.cjs", ".dependency-cruiser.js", ".dependency-cruiser.mjs"):
        config = next(n for n in (".dependency-cruiser.cjs", ".dependency-cruiser.js", ".dependency-cruiser.mjs") if (root / n).is_file())
        target = "src" if (root / "src").is_dir() else "*.js"
        out.append(
            recipe("ui-arch", "dependency-cruiser: the layering rules of the folder's config.", f"depcruise {target} --config {config}")
        )
    if _package_mentions(root, "vitest"):
        coverage = " --coverage" if _package_mentions(root, "coverage") else ""
        out.append(recipe("ui-test", "vitest, headless, run once.", f"vitest run{coverage}"))
    return out
