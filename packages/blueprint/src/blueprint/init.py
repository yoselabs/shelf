"""`blueprint init`: set a repo up from an installed blueprint, no shelf clone.

Four phases, in this order, each printed under its own name:

1. detect: scan the files for the stacks present, and say which files said so. A detected stack with no profile is an error, and so is a
   repo with no stack: the audit cannot judge what it cannot name, and the plan would be a guess.
2. audit: run every checkpoint, so the plan starts from what the repo already has.
3. plan: the steps that are missing, and only those.
4. apply: write them. A file the repo already has is never overwritten: `ruff.toml`, `pyrefly.toml`, a `[tool.ruff]` table, the
   `.pre-commit-config.yaml`, the justfile's own recipes stay as written. The one rewritten thing is the AGENTS.md managed block.

It ends with `left:`, the checkpoints that still do not pass, each with its remediation: what init could not set up. Exit 0 when none
is left, 1 when some are, 2 when it could not start. A second run on a finished repo writes nothing.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from blueprint import preset, render, templates
from blueprint.concerns import tool_pins
from blueprint.concerns.profile_data import load_profiles, profile_for
from blueprint.model import Context, Verdict
from blueprint.profile import detect, load_state
from blueprint.runner import run as audit_run

if TYPE_CHECKING:
    from collections.abc import Mapping

    from blueprint.model import Profile

RECIPES = Path(__file__).resolve().parent / "recipes"
_HOOK_CONFIG = ".pre-commit-config.yaml"
# What a stack or framework needs beside the justfile: the recipe file, and where the repo keeps its own copy of it. A copy the repo
# has is never rewritten: "the repo copies it and owns the copy".
RECIPE_TARGETS = {
    "dockerfile": (("check_dockerfile_pins.py", "tools/check_dockerfile_pins.py"),),
    "compose": (("compose_policy.rego", "policy/compose.rego"),),
    "dotnet": (("check_coverage.py", "tools/check_coverage.py"),),
    "godot": (("check_godot.py", "tools/check_godot.py"), ("godot-test.just", "tools/godot-test.just")),
    "unity": (("unity_integrity.py", "tools/unity_integrity.py"),),
}
_PYTHON = {"python-uv", "python"}
_LEFT = {Verdict.NOT_SET_UP, Verdict.FAILING}


def _profiled(stack: str) -> bool:
    return profile_for(stack, load_profiles()) is not None


def _out(text: str) -> None:
    sys.stdout.write(text + "\n")


def _tables(repo: Path) -> tuple[dict[str, object], bool]:
    """pyproject.toml parsed, and whether it parsed at all."""
    try:
        return tomllib.loads((repo / "pyproject.toml").read_text()), True
    except (OSError, tomllib.TOMLDecodeError):
        return {}, False


def _preset_text(repo: Path) -> tuple[str, list[str]]:
    """The `[tool.*]` tables of the packaged preset the repo lacks, as text to append, and the names of the ones it adds."""
    data, ok = _tables(repo)
    if not ok:
        return "", []
    reference = tomllib.loads(preset.REFERENCE.read_text())
    tool = data.get("tool", {})
    tool = tool if isinstance(tool, dict) else dict[str, object]()
    chunks: dict[str, str] = {}
    if "ruff" not in tool and not any((repo / n).is_file() for n in (".ruff.toml", "ruff.toml")):
        select, ignore = preset.toml_value(reference["ruff-select"]), preset.toml_value(reference["ruff-ignore"])
        chunks["tool.ruff.lint"] = f"[tool.ruff.lint]\nselect = {select}\nignore = {ignore}\n"
    if "pyrefly" not in tool and not (repo / "pyrefly.toml").is_file():
        kinds = "".join(f'{k} = "error"\n' for k in reference["pyrefly-errors"])
        chunks["tool.pyrefly.errors"] = f"[tool.pyrefly.errors]\n{kinds}"
    if "shelf-size" not in tool:
        caps = "".join(f"{k} = {v}\n" for k, v in reference["shelf-size"].items())
        chunks["tool.shelf-size"] = f"[tool.shelf-size]\n{caps}"
    return "\n".join(chunks.values()), list(chunks)


def _write_preset(repo: Path) -> list[str]:
    text, names = _preset_text(repo)
    if not names:
        return []
    path = repo / "pyproject.toml"
    before = path.read_text()
    path.write_text(before.rstrip("\n") + "\n\n" + text)
    if not _tables(repo)[1]:  # an appended table that breaks the file is undone: the owner's file wins
        path.write_text(before)
        return []
    return [f"pyproject.toml ({', '.join(names)})"]


def _hook_config_missing(repo: Path) -> bool:
    return not (repo / _HOOK_CONFIG).is_file()


def _write_hooks(repo: Path, env: Mapping[str, str]) -> list[str]:
    """The hook config when absent, then prek's own install; the latter only when prek is on PATH."""
    changed: list[str] = []
    if _hook_config_missing(repo):
        (repo / _HOOK_CONFIG).write_text((RECIPES / "pre-commit-config.yaml").read_text())
        changed.append(_HOOK_CONFIG)
    if shutil.which("prek", path=env.get("PATH")) is not None and changed:
        done = subprocess.run(["prek", "install"], cwd=repo, env=dict(env), capture_output=True, text=True, check=False)
        changed.append("git hooks (prek install)" if done.returncode == 0 else f"git hooks FAILED: {done.stderr.strip()}")
    return changed


def _recipes_missing(repo: Path, names: tuple[str, ...]) -> list[tuple[str, str]]:
    return [(src, dst) for name in names for src, dst in RECIPE_TARGETS.get(name, ()) if not (repo / dst).exists()]


def _write_recipes(repo: Path, names: tuple[str, ...]) -> list[str]:
    for src, dst in (missing := _recipes_missing(repo, names)):
        (repo / dst).parent.mkdir(parents=True, exist_ok=True)
        (repo / dst).write_text((RECIPES / src).read_text())
    return [dst for _, dst in missing]


def _kinds(profile: Profile) -> tuple[str, ...]:
    """The stacks and frameworks whose recipe files a repo may need."""
    return (*profile.stacks, *(name for name, _ in profile.frameworks))


_SAID = re.compile(r"\d+\.\d+\.\d+")
# tool -> the line mise.toml holds for it ({version} filled in); bd ships under another name.
_MISE_LINE = {"bd": '"github:gastownhall/beads" = {{ version = "{version}", bin = "bd" }}'}


def _installed_version(tool: str, env: Mapping[str, str]) -> str | None:
    """The x.y.z a tool on PATH says it is, the way the audit asks (`uv --version`, `bd --version`)."""
    argv = tool_pins.VERSION_ARGV.get(tool)
    if argv is None or shutil.which(argv[0], path=env.get("PATH")) is None:
        return None
    done = subprocess.run(argv, env=dict(env), capture_output=True, text=True, check=False, timeout=30)
    found = _SAID.search(done.stdout) if done.returncode == 0 else None
    return found.group() if found else None


def _mise_needed(repo: Path, profile: Profile, env: Mapping[str, str]) -> dict[str, str]:
    return tool_pins.needed(Context(repo=repo, profile=profile, env=dict(env)))


def _write_mise(repo: Path, profile: Profile, env: Mapping[str, str]) -> list[str]:
    """mise.toml pinning each tool the repo runs at the version found on PATH, then `mise lock`; a tool with no readable version is left."""
    lines = [
        _MISE_LINE.get(tool, '{tool} = "{version}"').format(tool=tool, version=version)
        for tool in _mise_needed(repo, profile, env)
        if (version := _installed_version(tool, env))
    ]
    if not lines:
        return []
    (repo / "mise.toml").write_text("[tools]\n" + "\n".join(lines) + "\n")
    changed = ["mise.toml"]
    if shutil.which("mise", path=env.get("PATH")) is not None:
        done = subprocess.run(["mise", "lock"], cwd=repo, env=dict(env), capture_output=True, text=True, check=False)
        changed.append("mise.lock" if done.returncode == 0 else f"mise.lock FAILED: {done.stderr.strip()}")
    return changed


def _write_beads(repo: Path, env: Mapping[str, str]) -> list[str]:
    """`bd init --skip-hooks` (bd never installs hooks: prek runs its events); the strict settings stay audit rows."""
    if shutil.which("bd", path=env.get("PATH")) is None:
        return ["beads FAILED: bd is not installed"]
    done = subprocess.run(["bd", "init", "--skip-hooks"], cwd=repo, env=dict(env), capture_output=True, text=True, check=False)
    return [".beads/ (bd init --skip-hooks)" if done.returncode == 0 else f"beads FAILED: {done.stderr.strip()}"]


def _plan(repo: Path, stacks: tuple[str, ...], env: Mapping[str, str], *, hooks: bool, beads: bool) -> list[str]:
    profile = detect(repo, load_state(repo))
    steps: list[str] = []
    missing_docs = [n for n in templates.required(profile) if not (repo / "docs" / "agents" / f"{n}.md").is_file()]
    agents = repo / "AGENTS.md"
    if missing_docs or not agents.is_file() or templates.block(profile) not in agents.read_text():
        steps.append("docs/agents files and the AGENTS.md block")
    if render.drift(repo):
        steps.append("the justfile parts (.blueprint/*.just)")
    if _PYTHON & set(stacks) and _preset_text(repo)[1]:
        steps.append("the linter preset tables absent from pyproject.toml")
    if _recipes_missing(repo, _kinds(profile)):
        steps.append("the stack's recipe files (tools/, policy/)")
    if hooks and _hook_config_missing(repo):
        steps.append("the hook config, then the git hooks")
    if beads and not (repo / ".beads").is_dir():
        steps.append("beads (bd init --skip-hooks)")
    if not (repo / "mise.toml").is_file() and _mise_needed(repo, profile, env):
        steps.append("mise.toml pins, from the versions of the tools on PATH")
    return steps


def _apply(repo: Path, stacks: tuple[str, ...], steps: list[str], env: Mapping[str, str], *, hooks: bool) -> list[str]:
    written: list[str] = []
    if any(s.startswith("docs/agents") for s in steps):
        written += templates.install(repo, detect(repo, load_state(repo)))
    if any(s.startswith("the justfile") for s in steps):
        written += render.write(repo)
    if any(s.startswith("the linter") for s in steps) and _PYTHON & set(stacks):
        written += _write_preset(repo)
    if any(s.startswith("the stack's recipe") for s in steps):
        written += _write_recipes(repo, _kinds(detect(repo, load_state(repo))))
    if hooks and any(s.startswith("the hook") for s in steps):
        written += _write_hooks(repo, env)
    if any(s.startswith("beads") for s in steps):
        written += _write_beads(repo, env)
    if any(s.startswith("mise.toml") for s in steps):  # last: the pins follow what the steps above made the repo run
        written += _write_mise(repo, detect(repo, load_state(repo)), env)
    return written


def run(repo: Path, *, hooks: bool = True, beads: bool = False, env: Mapping[str, str] | None = None) -> int:
    """detect, audit, plan, apply, then list what is left; the exit code of `blueprint init`."""
    repo = repo.expanduser().resolve()
    env = env if env is not None else dict(os.environ)
    profile = detect(repo, load_state(repo))
    if not profile.stacks:
        sys.stderr.write(f"init: no stack detected in {repo} (no manifest found); declare one in docs/blueprint/blueprint.toml\n")
        return 2
    files = dict(profile.stack_files)
    for stack in profile.stacks:
        _out(f"detect: {stack} ({files.get(stack, 'declared')})")
    if unprofiled := [s for s in profile.stacks if not _profiled(s)]:
        sys.stderr.write("".join(f"init: {s} has no profile: blueprint cannot set it up or judge it\n" for s in unprofiled))
        return 2
    first = audit_run(repo, env=dict(env))
    _out(f"audit: {sum(r.verdict in _LEFT for r in first.rows)} of {len(first.rows)} checkpoints not passing")
    steps = _plan(repo, profile.stacks, env, hooks=hooks, beads=beads)
    _out("plan: " + ("; ".join(steps) if steps else "nothing missing"))
    written = _apply(repo, profile.stacks, steps, env, hooks=hooks)
    _out("apply: " + (", ".join(written) if written else "nothing to write"))
    has_beads = beads or (repo / ".beads").is_dir()
    # Beads is the owner's choice: until it is made, its rows are a suggestion, not something init failed to set up.
    left = [r for r in audit_run(repo, env=dict(env)).rows if r.verdict in _LEFT and (has_beads or r.concern != "backlog")]
    prek_missing = hooks and shutil.which("prek", path=env.get("PATH")) is None and (repo / _HOOK_CONFIG).is_file()
    notes = ["hooks: prek is not installed, so no git hook was installed; run `mise install --locked`, then `prek install`"] * prek_missing
    notes += [] if hooks else ["hooks: not installed (--no-hooks); run `blueprint init` without --no-hooks to install them"]
    _out("left:" + ("" if left or notes else " nothing"))
    for note in notes:
        _out(f"  {note}")
    for row in left:
        _out(f"  {row.id}: {row.evidence} -> {row.remediation}")
    _out("suggested:")
    if not has_beads:
        _out("  beads tracks the work and is recommended: `blueprint init --beads` (runs `bd init --skip-hooks`; needs bd installed)")
    _out("  the shelf's packages (git+tag dependencies) are listed in its catalog/README.md: depend on one only when it wins")
    return 1 if left else 0
