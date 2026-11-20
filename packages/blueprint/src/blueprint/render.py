"""`blueprint render`: the justfile parts the blueprint owns, written per detected stack, and the drift check on them.

A repo's gate is its own `justfile` importing `.blueprint/base.just` and one `.blueprint/<stack>.just` per stack it has (ADR 0029: `import`,
not `mod`). The parts are plain text, rendered from the files under `just/` and the stacks detected: the same repo gives the same bytes, so
`blueprint render --check` can fail on any difference between what is committed and what the blueprint would write now. A consumer stops
copying recipe text: it re-renders, and the repo's own `justfile` keeps only what is its own.

Extension points, all in the repo's own justfile: a recipe defined there replaces the base or stack recipe of the same name
(`set allow-duplicate-recipes`), and `check-extra` runs one more thing in the gate.

Exit codes of the check: 0 current · 1 drift (a part differs, is missing, is stale, or the justfile does not import it).
"""

from __future__ import annotations

import sys
from pathlib import Path

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
    "python-uv": ("python", ("lint", "typecheck", "spell", "deps", "test")),
    "python": ("python", ("lint", "typecheck", "spell", "deps", "test")),
    "shell": ("shell", ("scripts",)),
}
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
    steps = [*_COMMON_STEPS, *(step for _, group in stack_parts for step in group)]
    base = (_TEMPLATES / "base.just").read_text().replace("@STEPS@", " ".join(f'"{s}"' for s in steps))
    rendered = {f"{FOLDER}/base.just": base}
    for name, _ in stack_parts:
        rendered[f"{FOLDER}/{name}.just"] = (_TEMPLATES / f"{name}.just").read_text()
    return rendered


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
    """The exit code of `blueprint render --check`."""
    found = drift(repo)
    if not found:
        sys.stdout.write(f"render: {repo.name}'s justfile parts are current\n")
        return 0
    sys.stderr.write(f"render: {len(found)} difference(s) from what the blueprint renders:\n")
    sys.stderr.write("".join(f"{line}\n" for line in found))
    sys.stderr.write("\nRun `uv run blueprint render` and commit the result.\n")
    return 1
