"""Backlog: beads is the one tracker, strict, quiet, and its content lints clean."""

from __future__ import annotations

import json

from blueprint.model import Context, Finding, FixedBy, Profile, check, failing, not_checked, not_set_up, passing

# Effective values bd must report (`bd config show --json`), owner rounds 5-8.
STRICT = {
    "no-git-ops": "true",
    "create.require-description": "true",
    "validation.on-create": "error",
    "validation.on-close": "error",
    "validation.metadata.mode": "error",
    "export.auto": "false",
    "export.git-add": "false",
    "import.auto": "false",
}
_METRICS_ENV = "BD_DISABLE_METRICS"


def _beads(profile: Profile) -> bool:
    return profile.tracker == "beads"


def _settings_env(ctx: Context) -> dict[str, str] | None:
    raw = ctx.read(".claude/settings.json")
    if raw is None:
        return {}
    try:
        env = json.loads(raw).get("env", {})
    except (json.JSONDecodeError, AttributeError):
        return None
    return {str(k): str(v) for k, v in env.items()} if isinstance(env, dict) else {}


_NO_BD = "install beads (https://github.com/gastownhall/beads) and run the audit from a clone with its database"


@check("backlog.tracker", "the repo tracks its work in beads")
def tracker(ctx: Context) -> Finding:
    """`.beads/config.yaml` exists."""
    if ctx.read(".beads/config.yaml") is None:
        return not_set_up("no .beads/config.yaml", "`bd init`, then apply the strict settings (backlog.strict-config)", FixedBy.AUTO)
    return passing("beads initialised (.beads/config.yaml)")


@check("backlog.strict-config", "bd's effective config is the strict set, none of it from the environment", applies=_beads, audit_only=True)
def strict_config(ctx: Context) -> Finding:
    """Every STRICT key has its value, and its source is the repo's config, not an env var."""
    done = ctx.run("bd", "config", "show", "--json", timeout=60)
    if done is None or done.returncode != 0:
        return not_checked("`bd config show --json` did not answer", _NO_BD)
    try:
        entries = {e["key"]: e for e in json.loads(done.stdout)}
    except (json.JSONDecodeError, KeyError, TypeError):
        return not_checked("`bd config show --json` printed something that is not its JSON")
    wrong: list[str] = []
    for key, want in STRICT.items():
        got = entries.get(key, {})
        if str(got.get("value")) != want:
            wrong.append(f"{key}={got.get('value', 'unset')} (want {want})")
        elif got.get("source") == "env":
            wrong.append(f"{key} comes from an env var, not .beads/config.yaml")
    if wrong:
        return failing(
            "; ".join(wrong),
            " && ".join(f"bd config set {k} {v}" for k, v in STRICT.items()) + "; then unset any BD_*/BEADS_* override",
            FixedBy.AUTO,
        )
    return passing(f"{len(STRICT)} strict settings in effect from .beads/config.yaml")


@check(
    "backlog.metrics-off",
    f"every agent session in the repo runs bd with metrics off ({_METRICS_ENV}=1 in .claude/settings.json)",
    applies=_beads,
)
def metrics_off(ctx: Context) -> Finding:
    """bd reads `metrics.disabled` only from the user config, so the repo turns it off through the session env."""
    env = _settings_env(ctx)
    if env is None:
        return failing(".claude/settings.json is not valid JSON", "fix the JSON")
    if env.get(_METRICS_ENV) != "1":
        return not_set_up(f'{_METRICS_ENV} is not "1" in .claude/settings.json env', f'add "env": {{"{_METRICS_ENV}": "1"}}', FixedBy.AUTO)
    return passing(f"{_METRICS_ENV}=1 in .claude/settings.json")


@check("backlog.no-tracked-export", "no beads JSONL export is tracked by git (the Dolt history is the record)", applies=_beads)
def no_tracked_export(ctx: Context) -> Finding:
    """`git ls-files .beads` lists no `*.jsonl`."""
    listed = ctx.git("ls-files", ".beads")
    if listed is None:
        return not_checked("not a git repository")
    tracked = [p for p in listed.splitlines() if p.endswith(".jsonl")]
    if tracked:
        return failing(
            f"tracked: {', '.join(tracked)}",
            f"git rm --cached {' '.join(tracked)}; add `*.jsonl` to .beads/.gitignore",
            FixedBy.AUTO,
        )
    return passing("no JSONL under .beads is tracked")


@check(
    "backlog.no-local-override",
    "nothing outside .beads/config.yaml weakens bd: no config.local.yaml, no BD_* in the session env",
    applies=_beads,
)
def no_local_override(ctx: Context) -> Finding:
    """`.beads/config.local.yaml` absent; .claude/settings.json env sets no BD_*/BEADS_* other than metrics."""
    problems: list[str] = []
    if ctx.path(".beads/config.local.yaml").exists():
        problems.append(".beads/config.local.yaml exists")
    env = _settings_env(ctx) or {}
    extra = sorted(k for k in env if k.startswith(("BD_", "BEADS_")) and k != _METRICS_ENV)
    if extra:
        problems.append(f".claude/settings.json env sets {', '.join(extra)}")
    if problems:
        return failing("; ".join(problems), "move the setting into .beads/config.yaml, or delete it")
    return passing("no local file or session env overrides bd")


@check("backlog.lint", "every open bead carries the sections bd requires (`bd lint` exits 0)", applies=_beads, audit_only=True)
def lint(ctx: Context) -> Finding:
    """`bd lint` passes."""
    done = ctx.run("bd", "lint", timeout=120)
    if done is None:
        return not_checked("`bd lint` did not answer", _NO_BD)
    if done.returncode != 0:
        first = (done.stdout.strip() or done.stderr.strip()).splitlines()[:3]
        return failing(
            f"`bd lint`: {' / '.join(first) or 'failed'}", "add the missing sections (acceptance criteria, description) to each bead named"
        )
    return passing("`bd lint` passes")


@check("backlog.no-tracker-file", "no second backlog: no TODO.md or docs/backlog.md beside beads", applies=lambda p: p.tracker is not None)
def no_tracker_file(ctx: Context) -> Finding:
    """Work lives in beads only."""
    found = [f for f in ("TODO.md", "TODO", "docs/backlog.md", "BACKLOG.md", "docs/todo.md") if ctx.path(f).exists()]
    if found:
        return failing(f"second backlog: {', '.join(found)}", "move each item into beads (`bd create`), then delete the file")
    return passing("beads is the only backlog")
