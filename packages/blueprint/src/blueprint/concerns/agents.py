"""Agents: the agent harness a repo carries: instructions, session settings, session hooks."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

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
