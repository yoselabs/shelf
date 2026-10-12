"""An application installed as a uv tool: its environment is resolved at install time and drifts from uv.lock.

`uv tool install --editable .` follows the source, not the lockfile: a dependency bump in uv.lock reaches
the tool only on a reinstall. `just check` runs in `.venv`, so it stays green while the installed tool
imports a name its old dependency lacks (a2kay: the daemon died on start, the KB MCP was down).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from blueprint import gate_graph
from blueprint.model import Finding, Sub, check_each, failing, not_applicable, not_checked, passing

if TYPE_CHECKING:
    from blueprint.model import Context, Profile

_ID = "stack.python-uv.uv-tool"
_STATEMENT = "an application installed as a uv tool has the dependency versions uv.lock pins"
_REINSTALL = "uv tool install --reinstall --editable ."
_INSTALL_RECIPES = ("install", "reinstall", "tool-install", "install-tool")


def _applies(profile: Profile) -> bool:
    """The repo is an application on the python-uv stack."""
    return profile.kind == "application" and "python-uv" in profile.stacks


def _norm(name: str) -> str:
    """PEP 503 normal form: how uv.lock and `uv pip list` may each spell one project."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _reinstall_step(ctx: Context) -> str | None:
    """The repo's own reinstall: a recipe running `uv tool install`, else a hook that does."""
    gate = gate_graph.load(ctx)
    if gate is not None:
        for name in _INSTALL_RECIPES:
            if name in gate.recipes and "uv tool install" in gate.recipes[name].body:
                return f"{gate.runner} {name}"
    return "the post-merge hook in .pre-commit-config.yaml" if "uv tool install" in (ctx.read(".pre-commit-config.yaml") or "") else None


def _single(finding: Finding) -> list[Sub]:
    return [Sub("stack/python-uv", _ID, _STATEMENT, finding)]


@check_each(_ID, _STATEMENT, audit_only=True, applies=_applies, layer="stack")
def uv_tool(ctx: Context) -> list[Sub]:
    """Compare the installed tool's environment with uv.lock, package by package."""
    project = ctx.toml("pyproject.toml").get("project")
    meta = project if isinstance(project, dict) else {}
    name = str(meta.get("name", ""))
    if not meta.get("scripts") or not name:
        return _single(not_applicable("no [project.scripts] entry point: nothing is installed as a uv tool"))
    tool_dir = ctx.run("uv", "tool", "dir", timeout=30)
    if tool_dir is None or tool_dir.returncode != 0:
        return _single(not_checked("`uv tool dir` did not answer: uv is not installed"))
    env = next((d for d in (Path(tool_dir.stdout.strip()) / n for n in (name, _norm(name))) if d.is_dir()), None)
    if env is None:
        return _single(not_applicable(f"{name} is not installed as a uv tool on this machine"))
    listed = ctx.run("uv", "pip", "list", "--python", str(env / "bin" / "python"), "--format", "json", timeout=60)
    installed: dict[str, str] = {}
    try:
        installed = {_norm(str(p["name"])): str(p["version"]) for p in json.loads(listed.stdout)} if listed else installed
    except (json.JSONDecodeError, KeyError, TypeError):
        installed = {}
    if not installed:
        return _single(not_checked(f"could not list the packages of the {name} tool environment"))
    raw = ctx.toml("uv.lock").get("package")
    packages: list[object] = raw if isinstance(raw, list) else []
    locked = {_norm(str(p["name"])): str(p["version"]) for p in packages if isinstance(p, dict) and "name" in p and "version" in p}
    drift = [f"{n} {v} (lock {locked[n]})" for n, v in sorted(installed.items()) if n in locked and n != _norm(name) and locked[n] != v]
    if not drift:
        return _single(passing(f"the {name} tool environment matches uv.lock ({len(installed)} packages)"))
    step = _reinstall_step(ctx)
    fix = (
        f"reinstall the tool: {step} (and keep it running after every lock change)"
        if step
        else f"`{_REINSTALL}` now; add a `just install` recipe running it and a post-merge hook that calls it, so a lock change reinstalls"
    )
    return _single(
        failing(
            f"the installed {name} tool differs from uv.lock: {', '.join(drift)}; `just check` uses .venv and cannot see it",
            fix,
        )
    )
