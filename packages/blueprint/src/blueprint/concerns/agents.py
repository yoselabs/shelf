"""Agents: the agent harness a repo carries: instructions, session settings, session hooks."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from blueprint import templates
from blueprint.model import FixedBy, check, failing, not_applicable, not_checked, not_set_up, passing, uses_beads

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


def _only_in(a: str, b: str) -> int:
    """How many distinct non-blank lines of `a` are missing from `b`."""
    theirs = {line.strip() for line in b.splitlines()}
    return len({line.strip() for line in a.splitlines() if line.strip()} - theirs)


def _lines(n: int) -> str:
    return f"{n} line{'' if n == 1 else 's'}"


def _no_agents_md(claude_text: str | None) -> Finding:
    if claude_text is not None:
        return not_set_up(
            "CLAUDE.md is the only instructions file; other agents read AGENTS.md",
            "mv CLAUDE.md AGENTS.md, then `ln -s AGENTS.md CLAUDE.md`",
        )
    return not_set_up("no AGENTS.md", "write AGENTS.md (the map and the working agreement), then `ln -s AGENTS.md CLAUDE.md`")


@check("agents.instructions", "AGENTS.md is the one instructions file; CLAUDE.md points to it", layer="agent", version=2)
def instructions(ctx: Context) -> Finding:
    """AGENTS.md exists; CLAUDE.md is absent, a symlink to it, or imports it."""
    agents = ctx.read("AGENTS.md")
    claude_text = ctx.read("CLAUDE.md")
    if agents is None:
        return _no_agents_md(claude_text)
    claude = ctx.path("CLAUDE.md")
    if claude.is_symlink() and claude.resolve() == ctx.path("AGENTS.md").resolve():
        return passing("CLAUDE.md is a symlink to AGENTS.md")
    if not claude.exists():
        return failing("no CLAUDE.md, so Claude Code does not read AGENTS.md", "ln -s AGENTS.md CLAUDE.md", FixedBy.AUTO)
    if "@AGENTS.md" in (claude_text or ""):
        return passing("CLAUDE.md imports @AGENTS.md")
    # Two files drift: each tool reads one, so the agents on one repo follow different rules.
    theirs, ours = _only_in(claude_text or "", agents), _only_in(agents, claude_text or "")
    if not theirs and not ours:
        return failing("CLAUDE.md is a copy of AGENTS.md: it drifts at the next edit", "ln -sf AGENTS.md CLAUDE.md", FixedBy.AUTO)
    return failing(
        f"CLAUDE.md is a second instructions file: {_lines(theirs)} only in CLAUDE.md, {_lines(ours)} only in AGENTS.md, "
        "so agents reading one get different rules than agents reading the other",
        "move what only CLAUDE.md holds into AGENTS.md (`diff AGENTS.md CLAUDE.md`), then `ln -sf AGENTS.md CLAUDE.md`",
    )


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


def _repo_gitignores(ctx: Context) -> list[str] | None:
    """Every .gitignore the repo tracks or would track (present and not ignored), or None outside a git repository."""
    listed = ctx.git("ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", ".gitignore", "**/.gitignore")
    return None if listed is None else sorted(p for p in listed.split("\0") if p)


# Where agent worktrees go: Claude Code's own folder, and the one blueprint prescribes for any harness.
_WORKTREE_DIRS = (".claude/worktrees/", ".worktrees/")


@check(
    "agents.worktrees",
    "every agent works in its own git worktree; the worktree folders are git-ignored",
    layer="agent",
    version=2,
)
def worktrees(ctx: Context) -> Finding:
    """Ignored, so no linter, test run or `git add -A` in the main checkout reaches into an agent's tree.

    Why worktrees at all: a commit hook hides uncommitted edits while it runs, so a second agent writing
    in the same checkout loses its write (reproduced with prek 0.3.6, 2026-10-11).
    """
    shared = _repo_gitignores(ctx)
    if shared is None:
        return not_checked("not a git repository")
    open_dirs = []
    with tempfile.TemporaryDirectory(prefix="blueprint-ignore-") as tmp:
        sandbox = Path(tmp)
        try:
            for rel in shared:
                source = ctx.path(rel)
                # Git reads only a regular file as a rule list: a symlinked .gitignore (dangling, to a folder, or to a
                # file) is ignored by git, and a listed file this tree lacks (git answering for another worktree) is no rule.
                if source.is_symlink() or not source.is_file():
                    continue
                (sandbox / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, sandbox / rel)
        except OSError as err:
            return not_checked(f"could not read the repo's .gitignore files: {type(err).__name__}: {err}")
        # A scratch repo holding only the repo's own .gitignore files: .git/info/exclude and the global
        # excludes file are clone-local, so a rule only they carry fails in the next clone.
        if ctx.run("git", "init", "-q", cwd=sandbox) is None:
            return failing("git did not run", "install git")
        for folder in _WORKTREE_DIRS:
            done = ctx.run("git", "-c", f"core.excludesFile={os.devnull}", "check-ignore", "-q", f"{folder}probe", cwd=sandbox)
            if done is None:
                return failing("git did not run", "install git")
            if done.returncode != 0:
                open_dirs.append(folder)
    if open_dirs:
        lines = "\\n".join(open_dirs)
        return not_set_up(
            f"not ignored by a .gitignore in the repo (.git/info/exclude and the global excludes do not count): {', '.join(open_dirs)}",
            f"printf '{lines}\\n' >> .gitignore",
            FixedBy.AUTO,
        )
    return passing(f"ignored: {', '.join(_WORKTREE_DIRS)}; the rule is in docs/agents/working-with-agents.md")


# A day: past it, a worktree's branch and main have moved apart far enough that merging is a
# second job. Overridable per repo (`worktree-sync-hours` in docs/blueprint/blueprint.toml settings).
_SYNC_HOURS = 24


def _branches(ctx: Context) -> list[str]:
    """The branches checked out in linked worktrees (the main checkout is not one)."""
    text = ctx.git("worktree", "list", "--porcelain") or ""
    blocks = [b for b in text.split("\n\n") if b.strip()][1:]
    return [line.removeprefix("branch refs/heads/") for b in blocks for line in b.splitlines() if line.startswith("branch ")]


def _oldest(ctx: Context, span: str) -> int | None:
    """Commit time of the oldest commit in `span` (`a..b`), or None when the span is empty."""
    out = ctx.git("log", "--format=%ct", span) or ""
    stamps = [int(s) for s in out.split()]
    return min(stamps) if stamps else None


@check(
    "agents.worktrees-in-sync",
    "every agent worktree merges into main and takes main's changes within a day",
    audit_only=True,
    layer="agent",
)
def worktrees_in_sync(ctx: Context) -> Finding:
    """Audit-only: reads this clone's worktrees. Fails on unmerged work, or missing main commits, older than a day.

    Why: worktrees that drift for days turn every merge into conflict resolution and let agents build
    on a main that no longer exists (owner, 2026-10-11).
    """
    branches = _branches(ctx)
    if not branches:
        return not_applicable("no linked worktrees")
    limit = time.time() - float(str(ctx.settings.get("worktree-sync-hours", _SYNC_HOURS))) * 3600
    stale: list[str] = []
    for branch in branches:
        unmerged = _oldest(ctx, f"main..{branch}")
        missing = _oldest(ctx, f"{branch}..main")
        if unmerged is not None and unmerged < limit:
            stale.append(f"{branch}: work unmerged since {_ago(unmerged)}")
        if missing is not None and missing < limit:
            stale.append(f"{branch}: behind main since {_ago(missing)}")
    if stale:
        return failing(
            "; ".join(stale),
            "in each worktree: rebase on main, `just check`, merge to main on the owner's yes; remove worktrees whose work is done",
        )
    return passing(f"{len(branches)} worktrees, each within {_SYNC_HOURS}h of main both ways")


def _ago(stamp: int) -> str:
    return f"{(time.time() - stamp) / 3600:.0f}h ago"


_INSTALL = "PYTHONPATH=<shelf>/packages/blueprint/src python3 -m blueprint template --repo ."


# What `bd init` writes into CLAUDE.md/AGENTS.md for the owner to fill: `_Add your build and test commands here_`
# (or `*...*`). Left in, agents get no build or test command.
_BD_PLACEHOLDER = re.compile(
    r"^[ \t>*_-]*[*_]\s*Add (?:your\b[^\n]*?\bhere|a brief overview\b[^\n]*?)[*_]\s*$", re.MULTILINE | re.IGNORECASE
)


def _instruction_files(ctx: Context) -> dict[str, str]:
    """AGENTS.md and CLAUDE.md by name; a symlink to the other is read once."""
    seen: dict[Path, str] = {}
    files: dict[str, str] = {}
    for name in ("AGENTS.md", "CLAUDE.md"):
        text = ctx.read(name)
        if text is not None and ctx.path(name).resolve() not in seen:
            seen[ctx.path(name).resolve()] = name
            files[name] = text
    return files


_FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
_BACKTICKED = re.compile(r"`([^`\n]+)`")
_LINKED = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
# A repo-relative file: no scheme, placeholder, glob or command; ends in a known extension; `NNNN` and `YYYY` are patterns.
_PATH = re.compile(r"[\w.-]+(?:/[\w.-]+)*\.(?:md|toml|ya?ml|json|py|sh|txt|just)")
_PATTERN = re.compile(r"N{2,}|YYYY|MM-DD")
_OPTIONAL = re.compile(r"\bif (?:it|one|they) exists?\b|\bif present\b|\bwhen present\b", re.IGNORECASE)


def _named_paths(text: str) -> list[str]:
    """The repo files a conventions file names in backticks or links, outside code fences, in first-seen order."""
    # A path named only "if it exists" (the domain template's CONTEXT-MAP.md) is optional, not a claim.
    prose = "\n".join(line for line in _FENCE.sub("", text).splitlines() if not _OPTIONAL.search(line))
    named = [*_BACKTICKED.findall(prose), *(t.split("#")[0] for t in _LINKED.findall(prose))]
    return list(dict.fromkeys(t for t in named if _PATH.fullmatch(t) and not _PATTERN.search(t)))


def _missing_paths(ctx: Context, name: str) -> list[str]:
    """Paths docs/agents/<name>.md names that exist neither from the repo root nor, for a link, beside the file."""
    here = Path("docs/agents")
    named = _named_paths(ctx.read(f"docs/agents/{name}.md") or "")
    return [p for p in named if not ctx.path(p).exists() and not ctx.path(str(here / p)).exists()]


@check(
    "agents.culture-files",
    "every docs/agents/ file the repo's profile requires exists; no template placeholder is left in it, AGENTS.md or CLAUDE.md; "
    "domain.md names only files that exist",
    layer="agent",
    version=3,
)
def culture_files(ctx: Context) -> Finding:
    """Missing files are not set up (auto: copied from the templates); a leftover `{{name}}` or bd template line is failing.

    domain.md also fails when it names a file the repo lacks (`docs/adr/INDEX.md`, `CONTEXT.md`): a template that
    contradicts the repo's real layout passes the placeholder test. Only domain.md is read: the other files name
    generated or optional paths (`.github/workflows/`, `recipes/...`) that a correct repo may not have.
    """
    names = templates.required(ctx.profile)
    missing = [n for n in names if ctx.read(f"docs/agents/{n}.md") is None]
    if missing:
        return not_set_up(f"missing docs/agents/: {', '.join(f'{n}.md' for n in missing)}", _INSTALL, FixedBy.AUTO)
    unfilled = [n for n in names if templates.PLACEHOLDER.search(ctx.read(f"docs/agents/{n}.md") or "")]
    if unfilled:
        return failing(f"placeholders left in: {', '.join(f'{n}.md' for n in unfilled)}", "fill each {{name}} from the repo")
    gone = _missing_paths(ctx, "domain")
    if gone:
        return failing(
            f"docs/agents/domain.md names files that do not exist: {', '.join(gone)}",
            "make the file exist (the standard layout is CONTEXT.md and docs/adr/, ADR 0017), or migrate the repo to it; "
            "a durable different layout needs an override backed by an accepted ADR",
        )
    left = {
        name: len(templates.PLACEHOLDER.findall(text)) + len(_BD_PLACEHOLDER.findall(text))
        for name, text in _instruction_files(ctx).items()
    }
    left = {name: n for name, n in left.items() if n}
    if left:
        where = ", ".join(f"{n} template placeholder{'' if n == 1 else 's'} in {name}" for name, n in left.items())
        return failing(
            where,
            "replace each `_Add your ... here_` or `{{name}}` line with the repo's real content "
            "(build and test: `just check`; architecture; conventions), or delete the heading",
        )
    return passing(f"{len(names)} conventions files: {', '.join(names)}; no placeholder in the instruction files")


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
