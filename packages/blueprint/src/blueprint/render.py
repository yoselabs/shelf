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
import shlex
import sys
import tomllib
from pathlib import Path
from typing import Any

from blueprint import gate_py, images_gate, node_gate
from blueprint.gate_graph import JUSTFILES
from blueprint.profile import detect_stacks, detected_stack_roots

FOLDER = ".blueprint"
_TEMPLATES = Path(__file__).resolve().parent / "just"
_STEP_DEFAULTS = Path(__file__).resolve().parent / "step_inputs.toml"
INPUTS_PART = f"{FOLDER}/step-inputs.toml"
_SETTING = "set allow-duplicate-recipes"
_HEADER = (
    "# The gate runner is just (ADR 0023), pinned as the `rust-just` dev dependency: `uv run just check`.\n"
    'set shell := ["bash", "-euo", "pipefail", "-c"]\n'
)

# stack -> (part name, the gate steps it adds to `check`, in order). A stack with no row has no recipes to render.
_STACKS = {
    "python-uv": ("python", ("lint-changed", "typecheck", "deps", "test")),
    "python": ("python", ("lint-changed", "typecheck", "deps", "test")),
    "shell": ("shell", ("scripts",)),
}
_STACK_INSTALLS = {
    "package-lock.json": "npm ci --no-audit --no-fund",
    "pnpm-lock.yaml": "pnpm install --frozen-lockfile",
    "yarn.lock": "yarn install --immutable",
}
# What the release gate runs instead of a step: the whole-history and whole-suite form.
_WHOLE = {"secrets": "secrets-all", "test": "test-all", "scripts": "scripts-all", "lint-changed": "lint", "deps": "deps-all"}
_COMMON_STEPS = ("blueprint", "secrets")


def _stack_parts(repo: Path) -> list[tuple[str, tuple[str, ...]]]:
    """The stack parts this repo has, in a fixed order, each once."""
    found = [_STACKS[s] for s in detect_stacks(repo) if s in _STACKS]
    seen: dict[str, tuple[str, ...]] = {}
    for name, steps in found:
        seen.setdefault(name, steps)
    return sorted(seen.items())


def _python_folder(repo: Path) -> str:
    """The folder of the Python stack ("." at the root, `backend` below it; ADR 0034), as detection finds it."""
    roots = dict(detected_stack_roots(repo))
    return roots.get("python-uv") or roots.get("python") or "."


_UV_RUN = re.compile(r"\buv run (?!--project)")


def _in_python_folder(rendered: dict[str, str], folder: str) -> dict[str, str]:
    """The parts of a repo whose Python stack lives in `folder` (ADR 0034).

    The Python recipes run in the folder (`[working-directory]`: just resolves it from the justfile's folder, imports included). Every
    other `uv run` stays at the repo root and names the project, so the repo-level steps (`any_gate`, `blueprint gate blueprint`) use
    the folder's environment: `--project` finds it without changing the directory.
    """
    marker = "[working-directory('@PY@')]\n"
    out: dict[str, str] = {}
    for name, text in rendered.items():
        if folder == ".":
            out[name] = text.replace(marker, "")
        else:
            out[name] = text.replace("@PY@", folder) if marker in text else _UV_RUN.sub(f"uv run --project {shlex.quote(folder)} ", text)
    return out


def parts(repo: Path) -> dict[str, str]:
    """`{path relative to the repo: text}` of every part this repo's stacks call for."""
    stack_parts = _stack_parts(repo)
    node = node_gate.plan(repo)
    contracts = _import_contracts(repo)
    images = images_gate.render(repo)
    generated = gate_py.generated(repo)
    steps = [
        *_COMMON_STEPS,
        *(step for name, group in stack_parts for step in (*group, *(("arch",) if name == "python" and contracts else ()))),
        *(node.steps if node else ()),
        *((images_gate.STEP,) if images else ()),
        *(f"generated-{g['name']}" for g in generated),
        *gate_py.extra_steps(repo),
    ]
    steps = list(dict.fromkeys(steps))
    whole: list[str] = [_WHOLE.get(s, s) for s in steps] if gate_py.release_gate(repo) else []
    base = (_TEMPLATES / "base.just").read_text()
    base = base.replace("@STEPS@", " ".join(f'"{s}"' for s in steps)).replace("@STEPS_ALL@", " ".join(f'"{s}"' for s in whole))
    installs = []
    for stack, folder in sorted(detected_stack_roots(repo)):
        if stack not in {"node", "node-tooling"}:
            continue
        command = next((cmd for lock, cmd in _STACK_INSTALLS.items() if (repo / folder / lock).is_file()), "")
        if command:
            installs.append(f"cd {shlex.quote(folder)} && {command}" if folder != "." else command)
    base = base.replace("@TOOLS@\n", "".join(f"    {line}\n" for line in installs))
    rendered = {f"{FOLDER}/base.just": base}
    if node:
        rendered[f"{FOLDER}/node.just"] = node.text
    if images:
        rendered[f"{FOLDER}/images.just"] = images
    if generated:
        rendered[f"{FOLDER}/generated.just"] = _generated_part(generated)
    py_folder = _python_folder(repo)
    if inputs := _step_inputs(steps, node.folder if node else ".", generated, py_folder):
        rendered[INPUTS_PART] = inputs
    for name, _ in stack_parts:
        text = (_TEMPLATES / f"{name}.just").read_text()
        rendered[f"{FOLDER}/{name}.just"] = text + (
            "\n" + (_TEMPLATES / "python_arch.just").read_text() if name == "python" and contracts else ""
        )
    if not gate_py.release_gate(repo):
        rendered = _without_release_recipes(repo, rendered, steps)
    return _in_python_folder(rendered, py_folder)


def _generated_inputs(entry: dict[str, Any]) -> list[str]:
    """A `generated-<name>` step's default inputs: its outputs, what it reads and pyproject (the declaration); `*` if none declared."""
    reads = [str(r) for r in entry.get("reads", [])]
    if not reads:
        return ["*"]
    outputs = [f"{o}/*" if not Path(str(o)).suffix else str(o) for o in entry.get("outputs", [])]
    return [*outputs, *reads, "*pyproject.toml"]


def _needs(entry: dict[str, Any]) -> str:
    """` recipe ...`: the recipes a generated step runs first, as just dependencies (a private one is fine); a non-name is dropped."""
    raw = entry.get("needs", [])
    names: list[str] = [n for n in raw if isinstance(n, str) and re.fullmatch(r"[A-Za-z_][\w-]*", n)] if isinstance(raw, list) else []
    return "".join(f" {n}" for n in names)


def _generated_part(generated: list[dict[str, Any]]) -> str:
    recipes = "\n\n".join(
        f"# {g['name']}: what `{g['command']}` writes into a temp folder equals the committed "
        f"{', '.join(map(str, g.get('outputs', [])))}.\n"
        f"[group('gate')]\ngenerated-{g['name']}:{_needs(g)}\n    uv run python -I -m blueprint.generated {g['name']}"
        for g in generated
    )
    return (
        "# Rendered by `blueprint gate render` -- never edit; a recipe of the same name in the repo's justfile replaces it\n"
        "# only through a declared override (gate.recipe-shadowing).\n"
        "# Generated files are current: each `[[tool.blueprint.gate.generated]]` entry is one step.\n\n" + recipes + "\n"
    )


def _python_root(repo: Path) -> Path:
    return repo / _python_folder(repo)


def _import_contracts(repo: Path) -> bool:
    """Whether the repo declares import-linter contracts: `[tool.importlinter]` in the root pyproject.toml, or a `.importlinter` file."""
    if (_python_root(repo) / ".importlinter").is_file():
        return True
    pyproject = gate_py.manifest(repo)
    if not pyproject.is_file():
        return False
    tool = tomllib.loads(pyproject.read_text()).get("tool", {})
    return isinstance(tool, dict) and "importlinter" in tool


# The steps that read only the Python stack's own folder: with the stack in `backend/` their globs are scoped to it, so an edit in the
# frontend starts none of them. `lint-changed` and `test` are `*` by default and scope to the folder too: a repo whose Python steps read
# files outside it (a unit that reads `frontend/*`, a root document to spell-check) widens them in its own `gate-inputs.toml`.
_PYTHON_STEPS = frozenset({"lint-changed", "typecheck", "deps", "arch", "test"})


def _scoped(step: str, globs: list[str], py_folder: str) -> list[str]:
    """`globs` of a Python step with the stack in `py_folder`: each under that folder (`*` becomes `backend/*`)."""
    if py_folder == "." or step not in _PYTHON_STEPS:
        return globs
    return [f"{py_folder}/{g}" for g in globs]


def _step_inputs(steps: list[str], node_folder: str = ".", generated: list[dict[str, Any]] | None = None, py_folder: str = ".") -> str:
    """The default input globs of the steps this gate runs that the blueprint knows, in the shape of the repo's `gate-inputs.toml`."""
    table = tomllib.loads(_STEP_DEFAULTS.read_text())
    wide = table.pop("wide", {})
    for g in generated or []:
        table[f"generated-{g['name']}"] = _generated_inputs(g)
    known = [s for s in dict.fromkeys(steps) if isinstance(table.get(s), list)]
    if not known:
        return ""
    lines = [
        "# Rendered by `blueprint gate render` -- never edit. The files each gate step reads (any-gate):",
        "# a step none of whose inputs changed is not started.",
        "# The repo's gate-inputs.toml holds only its exceptions: a list there widens a step, `[narrow]` with a reason narrows it.",
    ]
    glob = node_gate.inputs_folder(node_folder)
    scoped = {s: _scoped(s, list(dict.fromkeys(glob if g == "@NODE@/*" else g for g in table[s])), py_folder) for s in known}
    for s in known:
        globs = scoped[s]
        lines.append(f"{s} = [{', '.join(_quote(g) for g in (['*'] if '*' in globs else globs))}]")
    reasons = [s for s in known if s in wide and "*" in scoped[s]]
    if reasons:
        lines += ["", "[wide]", *(f"{s} = {_quote(wide[s])}" for s in reasons)]
    return "\n".join(lines) + "\n"


def _quote(text: str) -> str:
    """A TOML basic string for `text` (a glob or a reason: no control characters)."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _without_release_recipes(repo: Path, rendered: dict[str, str], steps: list[str]) -> dict[str, str]:
    """Drop release-only recipes, retaining any that the repo or another retained recipe references."""
    optional = {"check-all", "steps-all", "secrets-all", "scripts-all", "test-all", "deps-all"}
    blocks = {path: text.split("\n\n") for path, text in rendered.items()}
    recipe = re.compile(r"(?m)^([\w-]+)(?:\s+[^\n:]*)?:")
    references = set(steps) | _referenced_recipes(own_recipe_text(repo))
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


def own_recipe_text(repo: Path) -> str:
    """The consumer's just sources, following nested imports but excluding rendered blueprint parts."""
    pending = [repo / name for name in JUSTFILES]
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
    return next((repo / n for n in JUSTFILES if (repo / n).is_file()), repo / "justfile")


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
    lines += [_imports(name) for name in rendered if name.endswith(".just") and _imports(name) not in existing]
    if lines:
        head = "\n".join(lines).rstrip("\n") + "\n"
        justfile.write_text(head + ("\n" + existing if existing else ""))
        changed.append(justfile.name)
    return changed


def _present(repo: Path) -> list[str]:
    folder = repo / FOLDER
    return (
        sorted(f"{FOLDER}/{p.name}" for pattern in ("*.just", "step-inputs.toml") for p in folder.glob(pattern)) if folder.is_dir() else []
    )


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
    found += [f"  {justfile.name}: does not {_imports(name)}" for name in rendered if name.endswith(".just") and _imports(name) not in text]
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
