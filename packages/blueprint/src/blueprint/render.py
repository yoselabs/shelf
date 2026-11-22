"""`blueprint gate render`: the justfile parts the blueprint owns, written per detected stack, and the drift check on them.

A repo's gate is its own `justfile` importing `.blueprint/base.just` and one `.blueprint/<stack>.just` per stack it has (ADR 0029: `import`,
not `mod`). The parts are plain text, rendered from the files under `just/` and the stacks detected: the same repo gives the same bytes, so
`blueprint gate render --check` fails on any difference between what is committed and what the blueprint would write now. A consumer stops
copying recipe text: it re-renders, and the repo's own `justfile` keeps only what is its own.

Extension points: `check-extra` in the repo's justfile runs one more thing in the gate; `[tool.blueprint.gate]` in pyproject.toml holds
the repo's paths and extra steps (`gate_py`). A recipe defined there with a rendered name replaces it (`set allow-duplicate-recipes`),
but `gate.recipe-shadowing` fails that unless an `[[override]]` says why (ADR 0033).

Exit codes of the check: 0 current · 1 drift (a part differs, is missing, is stale, or the justfile does not import it).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from blueprint import gate_py
from blueprint.profile import detect_stacks

FOLDER = ".blueprint"
_TEMPLATES = Path(__file__).resolve().parent / "just"
_JUSTFILES = ("justfile", "Justfile", ".justfile")
_SETTING = "set allow-duplicate-recipes"
_HEADER = (
    "# The gate runner is just (ADR 0023), pinned as the `rust-just` dev dependency: `uv run just check`.\n"
    'set shell := ["bash", "-euo", "pipefail", "-c"]\n'
)

# stack -> (part name, the gate steps it adds to `check`, in order). A stack with no row has no recipes to render.
_STACKS = {
    "python-uv": ("python", ("lint-changed", "typecheck", "spell-changed", "deps", "test")),
    "python": ("python", ("lint-changed", "typecheck", "spell-changed", "deps", "test")),
    "shell": ("shell", ("scripts",)),
}
_STACK_INSTALLS = {
    "node": ("npm ci --no-audit --no-fund",),
    "node-tooling": ("npm ci --no-audit --no-fund",),
}
# What the release gate runs instead of a step: the whole-history and whole-suite form.
_WHOLE = {"secrets": "secrets-all", "test": "test-all", "scripts": "scripts-all", "lint-changed": "lint", "spell-changed": "spell"}
_COMMON_STEPS = ("guard", "preset", "render", "blueprint", "secrets")


def _stack_parts(repo: Path) -> list[tuple[str, tuple[str, ...]]]:
    """The stack parts this repo has, in a fixed order, each once."""
    found = [_STACKS[s] for s in detect_stacks(repo) if s in _STACKS]
    seen: dict[str, tuple[str, ...]] = {}
    for name, steps in found:
        seen.setdefault(name, steps)
    return sorted(seen.items())


def parts(repo: Path) -> dict[str, str]:
    """`{path relative to the repo: text}` of every part this repo's stacks call for."""
    stack_parts = _stack_parts(repo)
    steps = [*_COMMON_STEPS, *(step for _, group in stack_parts for step in group), *gate_py.extra_steps(repo)]
    whole: list[str] = [_WHOLE.get(s, s) for s in steps] if gate_py.release_gate(repo) else []
    base = (_TEMPLATES / "base.just").read_text()
    base = base.replace("@STEPS@", " ".join(f'"{s}"' for s in steps)).replace("@STEPS_ALL@", " ".join(f'"{s}"' for s in whole))
    installs = dict.fromkeys(line for stack in sorted(detect_stacks(repo)) for line in _STACK_INSTALLS.get(stack, ()))
    base = base.replace("@TOOLS@\n", "".join(f"    {line}\n" for line in installs))
    rendered = {f"{FOLDER}/base.just": base}
    for name, _ in stack_parts:
        rendered[f"{FOLDER}/{name}.just"] = (_TEMPLATES / f"{name}.just").read_text()
    if not gate_py.release_gate(repo):
        rendered = _without_release_recipes(repo, rendered, steps)
    return rendered


def _without_release_recipes(repo: Path, rendered: dict[str, str], steps: list[str]) -> dict[str, str]:
    """Drop release-only recipes, retaining any that the repo or another retained recipe references."""
    optional = {"check-all", "steps-all", "secrets-all", "scripts-all", "test-all", "lint", "spell"}
    blocks = {path: text.split("\n\n") for path, text in rendered.items()}
    recipe = re.compile(r"(?m)^([\w-]+)(?:\s+[^\n:]*)?:")
    references = set(steps) | _referenced_recipes(_own_recipe_text(repo))
    for groups in blocks.values():
        references |= _referenced_recipes("\n".join(b for b in groups if not (m := recipe.search(b)) or m[1] not in optional))
    retained: set[str] = set()
    while found := (optional - retained - {"check-all"}) & references:
        retained |= found
        added = "\n".join(b for groups in blocks.values() for b in groups if (m := recipe.search(b)) and m[1] in found)
        references |= _referenced_recipes(added)
    return {
        path: "\n\n".join(b for b in groups if not (m := recipe.search(b)) or m[1] not in optional - retained)
        for path, groups in blocks.items()
    }


def _referenced_recipes(text: str) -> set[str]:
    headers = re.findall(r"(?m)^[\w-]+(?:[^\n:]*)?:([^\n]*)", text)
    calls = re.findall(r"(?:\bjust\s+|{{\s*just_executable\(\)\s*}}\s+)([^\n]*)", text)
    return set(re.findall(r"[\w-]+", " ".join([*headers, *calls])))


def _own_recipe_text(repo: Path) -> str:
    pending = [repo / name for name in _JUSTFILES]
    seen: set[Path] = set()
    texts: list[str] = []
    while pending:
        path = pending.pop().resolve()
        if path in seen or not path.is_relative_to(repo.resolve()) or not path.is_file() or path.is_relative_to((repo / FOLDER).resolve()):
            continue
        seen.add(path)
        text = "\n".join(line for line in path.read_text().splitlines() if not line.lstrip().startswith("#"))
        texts.append(text)
        pending += [path.parent / name for name in re.findall(r"(?m)^import\??\s+['\"]([^'\"]+)['\"]", text)]
    return "\n".join(texts)


def _justfile(repo: Path) -> Path:
    return next((repo / n for n in _JUSTFILES if (repo / n).is_file()), repo / "justfile")


def _imports(name: str) -> str:
    return f"import '{name}'"


def write(repo: Path) -> list[str]:
    """Write every part, delete a stale one, and add the missing import lines to the repo's justfile (never touching the rest)."""
    rendered = parts(repo)
    (repo / FOLDER).mkdir(exist_ok=True)
    changed: list[str] = []
    for name, text in rendered.items():
        path = repo / name
        if not path.is_file() or path.read_text() != text:
            path.write_text(text)
            changed.append(name)
    for stale in sorted(set(_present(repo)) - set(rendered)):
        (repo / stale).unlink()
        changed.append(f"{stale} (removed)")
    justfile = _justfile(repo)
    existing = justfile.read_text() if justfile.is_file() else ""
    lines = [] if existing else [_HEADER]
    if _SETTING not in existing:
        lines.append(_SETTING)
    lines += [_imports(name) for name in rendered if _imports(name) not in existing]
    if lines:
        head = "\n".join(lines).rstrip("\n") + "\n"
        justfile.write_text(head + ("\n" + existing if existing else ""))
        changed.append(justfile.name)
    return changed


def _present(repo: Path) -> list[str]:
    folder = repo / FOLDER
    return sorted(f"{FOLDER}/{p.name}" for p in folder.glob("*.just")) if folder.is_dir() else []


def drift(repo: Path) -> list[str]:
    """What differs between the committed parts and what is rendered now, one line each."""
    rendered = parts(repo)
    found: list[str] = []
    for name, text in rendered.items():
        path = repo / name
        if not path.is_file():
            found.append(f"  {name}: missing")
        elif path.read_text() != text:
            found.append(f"  {name}: differs from what the blueprint renders (never hand-edit it; put the change in your own justfile)")
    found += [f"  {name}: no stack of this repo renders it" for name in sorted(set(_present(repo)) - set(rendered))]
    justfile = _justfile(repo)
    text = justfile.read_text() if justfile.is_file() else ""
    found += [f"  {justfile.name}: does not {_imports(name)}" for name in rendered if _imports(name) not in text]
    if _SETTING not in text:
        found.append(f"  {justfile.name}: does not `{_SETTING}` (a recipe of its own could not replace a base one)")
    return found


def check(repo: Path) -> int:
    """The exit code of `blueprint gate render --check`."""
    found = drift(repo)
    if not found:
        sys.stdout.write(f"render: {repo.name}'s justfile parts are current\n")
        return 0
    sys.stderr.write(f"render: {len(found)} difference(s) from what the blueprint renders:\n")
    sys.stderr.write("".join(f"{line}\n" for line in found))
    sys.stderr.write("\nRun `uv run blueprint gate render` and commit the result.\n")
    return 1
