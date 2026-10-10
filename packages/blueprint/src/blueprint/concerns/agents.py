"""Agents: the agent harness a repo carries: instructions, session settings, session hooks."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from blueprint import templates
from blueprint.model import FixedBy, check, failing, not_set_up, passing, uses_beads

if TYPE_CHECKING:
    from blueprint.model import Context, Finding

_METRICS_ENV = "BD_DISABLE_METRICS"
_SESSION_HOOKS = {
    "SessionStart": ("bd prime", "a SessionStart hook running `bd prime --hook-json`, so every session starts with the backlog"),
    "Stop": ("in_progress", "a Stop hook listing beads left in_progress, so no session ends with work silently open"),
}


def _settings(ctx: Context) -> dict[str, object] | None:
    raw = ctx.read(".claude/settings.json")
    if raw is None:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


@check("agents.instructions", "AGENTS.md is the one instructions file; CLAUDE.md points to it", layer="agent")
def instructions(ctx: Context) -> Finding:
    """AGENTS.md exists; CLAUDE.md is absent, a symlink to it, or imports it."""
    if ctx.read("AGENTS.md") is None:
        return not_set_up("no AGENTS.md", "write AGENTS.md (the map and the working agreement), then `ln -s AGENTS.md CLAUDE.md`")
    claude = ctx.path("CLAUDE.md")
    if claude.is_symlink() and claude.resolve() == ctx.path("AGENTS.md").resolve():
        return passing("CLAUDE.md is a symlink to AGENTS.md")
    if not claude.exists():
        return failing("no CLAUDE.md, so Claude Code does not read AGENTS.md", "ln -s AGENTS.md CLAUDE.md", FixedBy.AUTO)
    if "@AGENTS.md" in (ctx.read("CLAUDE.md") or ""):
        return passing("CLAUDE.md imports @AGENTS.md")
    return failing("CLAUDE.md is a second instructions file", "merge it into AGENTS.md, then `ln -sf AGENTS.md CLAUDE.md`")


@check(
    "agents.bd-metrics-off",
    f"every agent session runs bd with metrics off ({_METRICS_ENV}=1 in .claude/settings.json)",
    applies=uses_beads,
    layer="agent",
)
def bd_metrics_off(ctx: Context) -> Finding:
    """bd reads `metrics.disabled` only from the user config, so the repo turns it off through the session env."""
    settings = _settings(ctx)
    if settings is None:
        return failing(".claude/settings.json is not a JSON object", "fix the JSON")
    env = settings.get("env", {})
    if not isinstance(env, dict) or env.get(_METRICS_ENV) != "1":
        return not_set_up(f'{_METRICS_ENV} is not "1" in .claude/settings.json env', f'add "env": {{"{_METRICS_ENV}": "1"}}', FixedBy.AUTO)
    return passing(f"{_METRICS_ENV}=1 in .claude/settings.json")


@check(
    "agents.session-hooks",
    "Claude Code session hooks: SessionStart primes the backlog, Stop flags open work",
    applies=uses_beads,
    layer="agent",
)
def session_hooks(ctx: Context) -> Finding:
    """The two standard hooks in .claude/settings.json."""
    settings = _settings(ctx)
    if settings is None:
        return failing(".claude/settings.json is not a JSON object", "fix the JSON")
    hooks = json.dumps(settings.get("hooks", {}))
    missing = [why for event, (needle, why) in _SESSION_HOOKS.items() if f'"{event}"' not in hooks or needle not in hooks]
    if missing:
        return not_set_up(f"missing {'; '.join(missing)}", "copy both hooks from the shelf's .claude/settings.json", FixedBy.AUTO)
    return passing("SessionStart runs bd prime; Stop flags in-progress beads")


_INSTALL = "PYTHONPATH=<shelf>/packages/blueprint/src python3 -m blueprint template --repo ."


@check("agents.culture-files", "every docs/agents/ file the repo's profile requires exists, its placeholders filled", layer="agent")
def culture_files(ctx: Context) -> Finding:
    """Missing files are not set up (auto: copied from the templates); a leftover `{{name}}` is failing."""
    names = templates.required(ctx.profile)
    missing = [n for n in names if ctx.read(f"docs/agents/{n}.md") is None]
    if missing:
        return not_set_up(f"missing docs/agents/: {', '.join(f'{n}.md' for n in missing)}", _INSTALL, FixedBy.AUTO)
    unfilled = [n for n in names if templates.PLACEHOLDER.search(ctx.read(f"docs/agents/{n}.md") or "")]
    if unfilled:
        return failing(f"placeholders left in: {', '.join(f'{n}.md' for n in unfilled)}", "fill each {{name}} from the repo")
    return passing(f"{len(names)} conventions files: {', '.join(names)}")


@check("agents.managed-block", "AGENTS.md carries blueprint's managed block, current for this profile", layer="agent")
def managed_block(ctx: Context) -> Finding:
    """The block between the markers equals what the templates produce for this profile."""
    text = ctx.read("AGENTS.md") or ""
    if templates.BEGIN not in text or templates.END not in text:
        return not_set_up("AGENTS.md has no blueprint block", _INSTALL, FixedBy.AUTO)
    current = text[text.index(templates.BEGIN) : text.index(templates.END) + len(templates.END)].strip()
    if current != templates.block(ctx.profile).strip():
        return failing("the managed block differs from the template for this profile", _INSTALL, FixedBy.AUTO)
    return passing("managed block current")
