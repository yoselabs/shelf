"""Backlog: beads is the one tracker, strict, quiet, and its content lints clean."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from blueprint.concerns.git_hooks.gate_hooks import HOOK_CONFIG
from blueprint.model import Context, Finding, FixedBy, Profile, check, failing, not_checked, not_set_up, passing, uses_beads

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
    "dolt.auto-push": "true",
}
_METRICS_ENV = "BD_DISABLE_METRICS"
# `bd lint` prints a bead line (`<id> [<type>]: <title>`), then one `Missing: ## <section>` line per gap.
_LINT_MISSING = re.compile(r"Missing: ## (.+?)\s*$", re.MULTILINE)
_LINT_BLOCK = re.compile(r"^(\S+) \[[^\]]+\]:.*(?:\n(?!\S+ \[).*)*", re.MULTILINE)
_LINT_NAMED = 5


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


@check(
    "backlog.strict-config",
    "bd's effective config is the strict set, none of it from the environment",
    applies=uses_beads,
    audit_only=True,
    version=2,
)
def strict_config(ctx: Context) -> Finding:
    """Every STRICT key has its value, and its source is the repo's config, not an env var."""
    done = ctx.run("bd", "config", "show", "--json", timeout=60)
    if done is None or done.returncode != 0:
        return not_checked("`bd config show --json` did not answer", _NO_BD)
    try:
        shown = [(str(e["key"]), str(e["value"]), str(e.get("source", ""))) for e in json.loads(done.stdout)]
    except (json.JSONDecodeError, KeyError, TypeError):
        return not_checked("`bd config show --json` printed something that is not its JSON")
    wrong: list[str] = []
    for key, want in STRICT.items():
        seen = [(value, source) for k, value, source in shown if k == key]
        if not seen:
            wrong.append(f"{key} unset (want {want})")
            continue
        value, source = min(seen, key=_precedence)
        if value != want:
            wrong.append(f"{key}={value} (want {want})")
        elif source == "env":
            wrong.append(f"{key} comes from an env var, not .beads/config.yaml")
        elif source != "config.yaml":
            wrong.append(f"{key} comes from {source}, not .beads/config.yaml")
    if wrong:
        fix = _remediation(wrong)
        if ctx.path(".git").is_file():
            # A worktree's bd reads the main checkout's .beads (homelab: `bd where`), not the file this tree holds.
            fix += (
                "; in a git worktree bd reads the main checkout's .beads/config.yaml (`bd where`): the row passes once this branch merges"
            )
        return failing("; ".join(wrong), fix, FixedBy.AGENT)
    return passing(f"{len(STRICT)} strict settings in effect from .beads/config.yaml")


def _precedence(entry: tuple[str, str]) -> tuple[int, str, str]:
    """Sort key putting the entry bd acts on first, so the verdict never depends on the order bd lists duplicates in.

    bd prints a key once per source (the same key as `default` and `database`, in random order). Its own
    order for config keys is env, then .beads/config.yaml, then everything else. Only the first two
    reach a fresh clone, so the rest need no order of their own beyond being stable.
    """
    value, source = entry
    return ({"env": 0, "config.yaml": 1}.get(source, 2), source, value)


def _remediation(wrong: list[str]) -> str:
    keys = [k for k in STRICT if any(w.startswith((f"{k}=", f"{k} ")) for w in wrong)]
    lines = "; ".join(f"{k}: {STRICT[k]}" for k in keys)
    # `bd config set` writes bd's Dolt database for keys it does not own in config.yaml: a fresh clone never gets the value.
    return (
        f"edit .beads/config.yaml directly (a dotted key is nested YAML, `import.auto` is `import:` then `  auto: false`): {lines}; "
        "not `bd config set`, which writes bd's database; unset any BD_*/BEADS_* override, then confirm `bd config show --json` "
        'lists each with "source": "config.yaml"'
    )


_ROOT_LOCK = ".beads.gate.lock"


@check("backlog.lock-ignored", "bd's lock file beside .beads/ (.beads.gate.lock) is git-ignored", applies=uses_beads)
def lock_ignored(ctx: Context) -> Finding:
    """bd 1.3 writes it at the repo root on every run; unignored, it shows in `git status` and gets committed."""
    done = ctx.run("git", "check-ignore", "-q", "--no-index", _ROOT_LOCK)
    if done is None or done.returncode > 1:
        return ctx.not_a_repository()
    if done.returncode == 0:
        return passing(f"{_ROOT_LOCK} is git-ignored")
    return failing(f"{_ROOT_LOCK} is not git-ignored: bd writes it at the repo root", f"add `{_ROOT_LOCK}*` to .gitignore", FixedBy.AUTO)


@check("backlog.no-tracked-export", "no beads JSONL export is tracked by git (the Dolt history is the record)", applies=uses_beads)
def no_tracked_export(ctx: Context) -> Finding:
    """`git ls-files .beads` lists no `*.jsonl`."""
    listed = ctx.git("ls-files", ".beads")
    if listed is None:
        return ctx.not_a_repository()
    tracked = [p for p in listed.splitlines() if p.endswith(".jsonl")]
    if tracked:
        return failing(
            f"tracked: {', '.join(tracked)}",
            f"git rm --cached {' '.join(tracked)}; add `*.jsonl` to .beads/.gitignore",
            FixedBy.AUTO,
        )
    return passing("no JSONL under .beads is tracked")


@check("backlog.no-export-file", "no .beads/issues.jsonl on disk: it is a passive export, not a sync path", applies=uses_beads)
def no_export_file(ctx: Context) -> Finding:
    """The file may be gitignored and stale; beads sync is Dolt data at refs/dolt/data (`bd sync`), so nothing reads it."""
    if not ctx.path(".beads/issues.jsonl").exists():
        return passing("no .beads/issues.jsonl")
    return failing(
        ".beads/issues.jsonl exists: a passive export that nothing syncs from, so it only goes stale and misleads",
        "delete it (rm .beads/issues.jsonl); keep export.auto and export.git-add false (backlog.strict-config). Recovery is the Dolt "
        "remote (refs/dolt/data), pulled with `bd sync`, not this file",
    )


_SYNC_REMOTE = re.compile(r"^sync:\s*\n\s+remote:\s*['\"]?([^'\"\s]+)", re.MULTILINE)


def _same_place(url: str) -> str:
    """host/path of a git URL, transport, user and `.git` dropped: the https, ssh and scp forms of one repository agree."""
    plain = url.removeprefix("git+")
    found = re.match(r"^[\w.-]+@([\w.-]+):(.+)$", plain) or re.match(r"^[a-z+]+://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+)$", plain)
    if found is None:
        return plain
    return f"{found.group(1)}/{found.group(2)}".removesuffix(".git").strip("/").lower()


@check(
    "backlog.no-duplicate-remote",
    "`sync.remote` does not repeat git origin (bd derives the Dolt remote from origin; a copy drifts, e.g. ssh against https)",
    applies=uses_beads,
)
def no_duplicate_remote(ctx: Context) -> Finding:
    """A `sync.remote` naming the same repository as origin, in the same or another transport, is a second source of truth."""
    config = ctx.read(".beads/config.yaml")
    found = _SYNC_REMOTE.search(config or "")
    if found is None:
        return passing("no sync.remote: bd uses git origin")
    origin = ctx.git("remote", "get-url", "origin")
    if origin is None or not origin.strip():
        return passing("sync.remote is set and the repo has no git origin to repeat")
    remote = found.group(1)
    if _same_place(remote) != _same_place(origin.strip()):
        return passing("sync.remote names a different repository than origin")
    return failing(
        f"sync.remote {remote} repeats git origin {origin.strip()}"
        + ("" if remote.removeprefix("git+") == origin.strip() else " (only the transport differs)"),
        "delete the `sync:` block from .beads/config.yaml: bd takes the Dolt remote from git origin, so the clone's own transport "
        "always works; a copy goes wrong the day one machine uses ssh and another https",
    )


# bd's hooks run from the prek config (`bd hooks run <event>`), never installed by bd itself: bd appends its block to other
# managers' hook files, where a failing check then no longer blocks the commit (research/hooks-and-beads.md).
_BD_EVENTS = ("pre-commit", "post-merge", "pre-push", "post-checkout", "prepare-commit-msg")
_BEADS_MARKER = "BEGIN BEADS INTEGRATION"


@check(
    "backlog.hooks-recipe",
    "bd's five events run from the prek config (`bd hooks run <event>`), the config installs every stage, and no bd hook files are tracked",
    applies=uses_beads,
    version=1,
)
def hooks_recipe(ctx: Context) -> Finding:
    """The beads half of the hooks recipe, split out of gate.hooks-recipe so git-hooks knows nothing of beads."""
    config = ctx.read(HOOK_CONFIG)
    if config is None:
        return not_set_up(
            f"no {HOOK_CONFIG}", "`uv run blueprint init` writes the recipe (gate.hooks-recipe asks for it too)", FixedBy.AUTO
        )
    problems: list[str] = []
    tracked = (ctx.git("ls-files", ".beads/hooks", ".beads-hooks") or "").split()
    if tracked:
        problems.append(f"bd's own hook files are tracked ({len(tracked)}): git rm -r --cached .beads/hooks")
    missing = [e for e in _BD_EVENTS if f"bd hooks run {e}" not in config]
    if missing:
        problems.append(f"bd events not run from {HOOK_CONFIG}: {', '.join(missing)}")
    if "default_install_hook_types" not in config:
        problems.append("no default_install_hook_types, so `prek install` installs pre-commit only")
    if problems:
        return failing(
            "; ".join(problems),
            f"merge the recipe's bd `repo: local` block first under `repos:` in {HOOK_CONFIG} and `default_install_hook_types` at the top, "
            "keeping the hooks the repo already has (`blueprint init` writes the recipe); then `prek install`",
        )
    return passing(f"{HOOK_CONFIG} runs bd's five events")


@check(
    "backlog.hooks-installed",
    "bd has injected no block into the installed git hooks",
    applies=uses_beads,
    audit_only=True,
    version=1,
)
def hooks_installed(ctx: Context) -> Finding:
    """The beads half of gate.hooks-installed: bd's own block in a hook file means a failing check no longer blocks."""
    if ctx.git("rev-parse", "--git-dir") is None:
        return ctx.not_a_repository()
    hooks_dir = Path((ctx.git("rev-parse", "--git-path", "hooks") or ".git/hooks").strip())
    hooks_dir = hooks_dir if hooks_dir.is_absolute() else ctx.repo / hooks_dir
    if not hooks_dir.is_dir():
        return passing("no hooks directory, so nothing injected")
    injected = sorted(
        p.name for p in hooks_dir.iterdir() if p.is_file() and _BEADS_MARKER in p.read_text(encoding="utf-8", errors="replace")
    )  # lossy-ok: parse: the text is matched for a yes/no, never stored or hashed
    if injected:
        return failing(f"bd injected its block into {', '.join(injected)}", "bd hooks uninstall; prek install", FixedBy.AUTO)
    return passing("no bd block in the installed hooks")


@check(
    "backlog.worktree-database",
    "a linked git worktree holds no bd database of its own: every worktree shares the main checkout's",
    applies=uses_beads,
)
def worktree_database(ctx: Context) -> Finding:
    """`.git` is a file in a linked worktree; an `.beads/embeddeddolt` there is a private, empty copy that loses what is written to it."""
    if not ctx.path(".git").is_file():
        return passing("not a linked worktree")
    if not ctx.path(".beads/embeddeddolt").exists():
        return passing("this worktree uses the main checkout's bd database")
    return failing(
        ".beads/embeddeddolt exists in this worktree: bd has a private database here (BEADS_DIR set to this worktree, or bd init or "
        "bootstrap run here); beads written to it are lost with the worktree and auto-push warns `remote 'origin' not found`",
        "check it holds nothing you need (`BEADS_DIR=$PWD/.beads bd stats`), then "
        "`rm -rf .beads/embeddeddolt .beads/backup .beads/push-state.json`; unset BEADS_DIR; "
        "`bd where` must then name the main checkout's .beads/embeddeddolt",
    )


@check(
    "backlog.no-local-override",
    "nothing outside .beads/config.yaml weakens bd: no config.local.yaml, no BD_* in the session env",
    applies=uses_beads,
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


# Criteria are what make a bead ready to start, so the beads still to be started are linted: `open` (bd's default) and
# `blocked` (it turns ready when its blocker closes). Work already claimed is past that gate, and a deferred idea may stay
# unfinished (owner, 2026-10-11).
LINTED_STATUSES = ("open", "blocked")


@check(
    "backlog.lint",
    "every bead still to be started (open or blocked) carries the sections bd requires (`bd lint` exits 0)",
    applies=uses_beads,
    audit_only=True,
    version=2,
)
def lint(ctx: Context) -> Finding:
    """bd's database answers, then `bd lint` passes for each status still to be started."""
    probe = ctx.run("bd", "list", "--limit", "1", "--json", timeout=60)
    if probe is None:
        return not_checked("`bd` did not answer", _NO_BD)
    if probe.returncode != 0:
        # On a database that is missing or uninitialized `bd lint` checks 0 issues and exits 0 (a2kay, shelf-9g7).
        cause = next((ln.strip() for ln in (probe.stderr + probe.stdout).splitlines() if ln.strip().startswith("Error")), "bd list failed")
        fix = (
            "in a fresh clone, in order: `mise trust --yes && mise install --locked` (until trusted every mise shim refuses, bd "
            "included), then `bd bootstrap` (pulls the database from refs/dolt/data); then re-run"
        )
        if "not initialized" in cause:
            # bd bootstrap calls an existing but uninitialized database "nothing to do" (a2kay, shelf-9g7).
            fix = "the local database exists but is broken: mv .beads/embeddeddolt .beads/embeddeddolt.broken, then bd bootstrap"
        return failing(f"bd's database does not answer in this clone: {cause}", fix)
    failed: list[str] = []
    for status in LINTED_STATUSES:
        done = ctx.run("bd", "lint", "--status", status, timeout=120)
        if done is None:
            return not_checked("`bd lint` did not answer", _NO_BD)
        if done.returncode != 0:
            failed.append(done.stdout or done.stderr)
    if failed:
        return failing(_lint_evidence("\n".join(failed)), "add the missing sections (acceptance criteria, description) to each bead named")
    return passing(f"`bd lint` passes for {', '.join(LINTED_STATUSES)} beads")


def _lint_evidence(output: str) -> str:
    """The count of beads and of each missing section, and the first few bead ids: enough to size the cleanup."""
    # One block per bead (its header, then its Missing lines); a bead two runs both report counts once.
    blocks = {m.group(1): m.group(0) for m in _LINT_BLOCK.finditer(output)}
    beads = list(blocks)
    sections = Counter(name for block in blocks.values() for name in _LINT_MISSING.findall(block))
    if not beads:
        # Not the format we know: the first non-blank lines are still better than nothing.
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        return f"`bd lint`: {' / '.join(lines[:3]) or 'failed'}"
    counts = ", ".join(f"{name} x{n}" for name, n in sorted(sections.items())) or "see `bd lint`"
    return f"{len(beads)} beads miss sections: {counts}; first: {', '.join(beads[:_LINT_NAMED])}"


def _has_tracker(profile: Profile) -> bool:
    """The repo names an issue tracker."""
    return profile.tracker is not None


@check("backlog.no-tracker-file", "no second backlog: no TODO.md or docs/backlog.md beside beads", applies=_has_tracker)
def no_tracker_file(ctx: Context) -> Finding:
    """Work lives in beads only."""
    found = [f for f in ("TODO.md", "TODO", "docs/backlog.md", "BACKLOG.md", "docs/todo.md") if ctx.path(f).exists()]
    if found:
        return failing(f"second backlog: {', '.join(found)}", "move each item into beads (`bd create`), then delete the file")
    return passing("beads is the only backlog")


# The fixer hook seen failing on bd's own files: `bd bootstrap` leaves .beads/metadata.json without a final newline, so
# end-of-file-fixer over every file failed `just check` in each fresh clone (homelab, 2026-10-11). Other fixers join the
# list when one is seen failing there, not before.
_FIXERS = ("end-of-file-fixer",)
_HOOK_ID = re.compile(r"^(\s*)-\s*id:\s*([\w-]+)", re.MULTILINE)


def _spares_beads(block: str) -> bool:
    return any(".beads" in line for line in block.splitlines() if line.strip().startswith("exclude:"))


@check("backlog.hooks-spare-beads", "an end-of-file-fixer hook excludes .beads/, which bd writes", applies=uses_beads)
def hooks_spare_beads(ctx: Context) -> Finding:
    """end-of-file-fixer carries `exclude: ^\\.beads/`, or the config's top-level exclude does."""
    text = ctx.read(".pre-commit-config.yaml") or ""
    top = "\n".join(line for line in text.splitlines() if line.startswith("exclude:"))
    starts = list(_HOOK_ID.finditer(text))
    ends: list[int] = [found.start() for found in starts[1:]] + [len(text)] if starts else []
    bare = [
        found.group(2)
        for found, end in zip(starts, ends, strict=True)
        if found.group(2) in _FIXERS and not _spares_beads(text[found.end() : end])
    ]
    if bare and not _spares_beads(top):
        return failing(
            f"{', '.join(bare)} run over .beads/, which bd rewrites (a fresh clone's `bd bootstrap` fails them)",
            "add `exclude: ^\\.beads/` to each of those hooks in .pre-commit-config.yaml",
        )
    return passing("no end-of-file-fixer reaches .beads/")
