"""Tool pins: every tool the repo runs is pinned exactly in mise.toml, locked in mise.lock, installed at that version.

ADR 0024. Two machines sharing one Dolt remote ran bd 1.1.2 and 1.3.1, and the newer one migrated the schema
under the older; just, prek and the Godot editor had no pin at all. mise pins them; the languages keep their
own pin files (`.python-version` is uv's, `global.json` is the .NET SDK's), and just stays with uv where it is
the `rust-just` dev dependency (ADR 0023), so nothing is pinned twice.
Research: openspec/changes/blueprint-skill/research/toolchain-installer.md.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from blueprint import gate_graph
from blueprint.model import check, failing, not_applicable, not_set_up, passing, toml_table, uses_beads

if TYPE_CHECKING:
    from blueprint.model import Context, Finding

_MISE, _LOCK = "mise.toml", "mise.lock"
# An exact version: three numbers, then anything (`4.7.2-stable`); `latest`, `1.58` or `^1` are ranges to mise.
_EXACT = re.compile(r"^v?\d+\.\d+\.\d+")
_NUMBERS = re.compile(r"\d+(?:\.\d+)*")
# The first x.y.z a tool prints is its own version (`bd version 1.3.1 (c1c4b642a)`, `git-lfs/3.7.1 (...; go 1.25.3)`).
_SAID = re.compile(r"\d+\.\d+\.\d+")
_FLOOR = re.compile(r">=\s*(\d+(?:\.\d+)*)")
# A tool's mise key names its source (`github:gastownhall/beads`); these sources ship the tool under another name.
_ALIASES = {"beads": "bd"}
# How each tool says its version, for the audit; a tool not listed here is not asked.
_VERSION_ARGV = {
    "uv": ("uv", "--version"),
    "just": ("just", "--version"),
    "prek": ("prek", "--version"),
    "bd": ("bd", "--version"),
    "git-lfs": ("git", "lfs", "version"),
    "gitleaks": ("gitleaks", "version"),
    "godot": ("godot", "--version"),
}
_INSTALL = 'a recipe (`just tools`) that runs `MISE_IGNORED_CONFIG_PATHS="$HOME/.config/mise" mise install --locked`'


def _rust_just(ctx: Context) -> bool:
    """Whether just comes from uv: `rust-just` in a dependency group of the root pyproject."""
    groups = toml_table(ctx.toml("pyproject.toml"), "dependency-groups")
    return any(isinstance(deps, list) and any(str(d).startswith("rust-just") for d in deps) for deps in groups.values())


def _needed(ctx: Context) -> dict[str, str]:
    """Each tool the repo runs, with what says so."""
    needed: dict[str, str] = {}
    if "python-uv" in ctx.profile.stacks:
        needed["uv"] = "uv.lock"
    if ctx.read(".pre-commit-config.yaml") is not None:
        needed["prek"] = ".pre-commit-config.yaml"
    if uses_beads(ctx.profile):
        needed["bd"] = ".beads/"
    if ctx.read("justfile") is not None and not _rust_just(ctx):
        needed["just"] = "justfile"
    # A gitleaks hook from its own repo is pinned by the hook's `rev`; one the justfile runs comes from mise.
    recipes = "\n".join(line for line in (ctx.read("justfile") or "").splitlines() if not line.lstrip().startswith("#"))
    if "gitleaks" in recipes:
        needed["gitleaks"] = "justfile"
    # git-lfs is deliberately absent: git runs it as a filter during `git clone`, before `mise trust` can run, so a mise
    # shim breaks cloning an untrusted checkout (lifesim, 2026-10-12). It comes from the system package manager.
    if any(name == "godot" for name, _ in ctx.profile.frameworks):
        needed["godot"] = "project.godot"
    return needed


def _name(key: str, spec: object) -> str:
    """The tool a mise entry installs: its `bin`/`rename_exe`, else the last part of its key."""
    named = (spec.get("rename_exe") or spec.get("bin")) if isinstance(spec, dict) else None
    tail = re.split(r"[:/]", key)[-1]
    return str(named) if named else _ALIASES.get(tail, tail)


def _version(spec: object) -> str:
    return str(spec.get("version", "")) if isinstance(spec, dict) else str(spec)


def _numbers(text: str) -> tuple[int, ...]:
    found = _NUMBERS.search(text)
    return tuple(int(n) for n in found.group().split(".")) if found else ()


def _pins(ctx: Context) -> dict[str, tuple[str, str]]:
    """tool name -> (mise key, pinned version)."""
    return {_name(key, spec): (key, _version(spec)) for key, spec in toml_table(ctx.toml(_MISE), "tools").items()}


def _locked(ctx: Context) -> dict[str, set[str]]:
    """mise key -> the versions mise.lock holds for it."""
    found: dict[str, set[str]] = {}
    for key, entries in toml_table(ctx.toml(_LOCK), "tools").items():
        rows = entries if isinstance(entries, list) else [entries]
        found[key] = {str(e.get("version", "")) for e in rows if isinstance(e, dict)}
    return found


def _godot_sdk(ctx: Context) -> str | None:
    """The Godot.NET.Sdk version a csproj beside project.godot pins."""
    for _, root in ctx.profile.frameworks:
        for csproj in sorted(ctx.path(root).glob("*.csproj")):
            if found := re.search(r"Godot\.NET\.Sdk/(\d+\.\d+\.\d+)", csproj.read_text(errors="replace")):
                return found.group(1)
    return None


def _cross_file(ctx: Context, pins: dict[str, tuple[str, str]]) -> list[str]:
    """Pins that disagree with the language pin files, or are pinned twice."""
    problems: list[str] = []
    if "python" in pins and ctx.read(".python-version") is not None:
        problems.append("python is pinned in mise.toml; .python-version is the pin (uv installs Python)")
    if "dotnet" in pins and ctx.read("global.json") is not None:
        problems.append("dotnet is pinned in mise.toml; global.json is the pin (mise reads it: idiomatic_version_file_enable_tools)")
    if "just" in pins and _rust_just(ctx):
        problems.append("just is pinned twice: in mise.toml and as the rust-just dev dependency; keep one")
    floor = _FLOOR.search(str(toml_table(ctx.toml("pyproject.toml"), "tool", "uv").get("required-version", "")))
    if "uv" in pins and floor and _numbers(pins["uv"][1]) < _numbers(floor.group(1)):
        problems.append(f"uv {pins['uv'][1]} is below [tool.uv] required-version {floor.group()}")
    sdk = _godot_sdk(ctx)
    if "godot" in pins and sdk and not pins["godot"][1].removeprefix("v").startswith(sdk):
        problems.append(f"godot {pins['godot'][1]} differs from the csproj's Godot.NET.Sdk/{sdk}")
    return problems


def _example(needed: dict[str, str]) -> str:
    return " ".join(f'{tool} = "x.y.z"' for tool in needed)


def _installs_locked(ctx: Context) -> bool:
    """Whether a recipe of the gate's file installs the lock (any name: `bootstrap` often means onboarding already)."""
    gate = gate_graph.load(ctx)
    return gate is not None and "mise install --locked" in gate.text


@check("stack.tool-pins", "every tool the repo runs is pinned exactly in mise.toml and locked in mise.lock", layer="stack")
def tool_pins(ctx: Context) -> Finding:
    """Read mise.toml and mise.lock against the tools the repo's files say it runs; no network."""
    needed = _needed(ctx)
    if not needed:
        return not_applicable("the repo runs no tool blueprint pins (uv, just, prek, bd, godot)")
    wanted = ", ".join(f"{tool} ({why})" for tool, why in needed.items())
    if ctx.read(_MISE) is None:
        return not_set_up(
            f"no mise.toml; the repo runs {wanted}",
            f"write mise.toml with an exact version per tool ([tools] {_example(needed)}), "
            f"run `mise lock`, commit both, and add {_INSTALL} (ADR 0024)",
        )
    pins = _pins(ctx)
    problems = [f"{tool} is not pinned (the repo runs it: {why})" for tool, why in needed.items() if tool not in pins]
    problems += [f"{tool} {version!r} is not an exact version" for tool, (_, version) in pins.items() if not _EXACT.match(version)]
    problems += _cross_file(ctx, pins)
    if "git-lfs" in pins:
        problems.append(
            "git-lfs is pinned in mise.toml: its shim breaks `git clone` in an untrusted checkout "
            "(git calls it as a filter before `mise trust` can run); remove the pin and install git-lfs with the system package manager"
        )
    if ctx.read(_LOCK) is None:
        problems.append("no mise.lock: run `mise lock` and commit it")
    else:
        locked = _locked(ctx)
        problems += [
            f"{tool} {version} is not in mise.lock (run `mise lock`)"
            for tool, (key, version) in pins.items()
            if version not in locked.get(key, set())
        ]
    if not _installs_locked(ctx):
        problems.append(f"no {_INSTALL}: the user's own `latest` tools would make `--locked` fail")
    if problems:
        return failing("; ".join(problems), "fix each pin in mise.toml, then `mise lock` and commit both (ADR 0024)")
    return passing(f"{len(pins)} tools pinned and locked: " + ", ".join(f"{t} {v}" for t, (_, v) in sorted(pins.items())))


@check(
    "stack.tools-installed",
    "each pinned tool on this machine's PATH is the version mise.toml pins",
    audit_only=True,
    layer="stack",
)
def tools_installed(ctx: Context) -> Finding:
    """Ask each pinned tool its version through PATH, the way the gate will find it."""
    pins = {t: v for t, (_, v) in _pins(ctx).items() if t in _VERSION_ARGV}
    if not pins:
        return not_applicable("mise.toml pins no tool blueprint knows how to ask for its version")
    drift: list[str] = []
    for tool, pinned in sorted(pins.items()):
        done = ctx.run(*_VERSION_ARGV[tool], timeout=30)
        said = _SAID.search(done.stdout) if done is not None and done.returncode == 0 else None
        if said is None:
            drift.append(f"{tool} is not installed")
        elif _numbers(said.group()) != _numbers(pinned.removeprefix("v")):
            drift.append(f"{tool} {said.group()} (pin {pinned})")
    if drift:
        return failing(
            "; ".join(drift) + " on this machine's PATH",
            'run `just tools` (mise install --locked), then put mise first on PATH: `eval "$(mise activate zsh)"` (or bash) in the '
            "shell's rc file, or prepend ~/.local/share/mise/shims; a brew or system copy earlier on PATH wins otherwise",
        )
    return passing("installed as pinned: " + ", ".join(f"{t} {v}" for t, v in pins.items()))
