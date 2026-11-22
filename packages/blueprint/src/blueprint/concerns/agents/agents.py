"""Agents: the agent harness a repo carries: instructions, session settings, session hooks."""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from blueprint.model import FixedBy, check, failing, not_applicable, not_checked, not_set_up, passing

if TYPE_CHECKING:
    from blueprint.model import Context, Finding


def _only_in(a: str, b: str) -> int:
    """How many distinct non-blank lines of `a` are missing from `b`."""
    theirs = {line.strip() for line in b.splitlines()}
    return len({line.strip() for line in a.splitlines() if line.strip()} - theirs)


def _lines(n: int) -> str:
    return f"{n} line{'' if n == 1 else 's'}"


def _no_agents_md(claude_text: str | None) -> Finding:
    if claude_text is not None:
        return not_set_up("CLAUDE.md is the only instructions file; AGENTS.md is the one", "git mv CLAUDE.md AGENTS.md")
    return not_set_up("no AGENTS.md", "write AGENTS.md (the map and the working agreement)")


@check("agents.instructions", "AGENTS.md is the only instructions file; there is no CLAUDE.md", layer="agent", version=3)
def instructions(ctx: Context) -> Finding:
    """AGENTS.md exists and CLAUDE.md does not (owner, 2026-11-20): a CLAUDE.md in any form, file, copy or symlink, is a second home."""
    agents = ctx.read("AGENTS.md")
    claude_text = ctx.read("CLAUDE.md")
    if agents is None:
        return _no_agents_md(claude_text)
    claude = ctx.path("CLAUDE.md")
    if not claude.exists() and not claude.is_symlink():
        return passing("AGENTS.md is the only instructions file (no CLAUDE.md)")
    if claude.is_symlink():
        return failing("CLAUDE.md is a symlink to AGENTS.md: the repo has one instructions file", "git rm CLAUDE.md", FixedBy.AUTO)
    theirs, ours = _only_in(claude_text or "", agents), _only_in(agents, claude_text or "")
    if not theirs and not ours:
        return failing("CLAUDE.md is a copy of AGENTS.md: it drifts at the next edit", "git rm CLAUDE.md", FixedBy.AUTO)
    return failing(
        f"CLAUDE.md is a second instructions file: {_lines(theirs)} only in CLAUDE.md, {_lines(ours)} only in AGENTS.md, "
        "so agents reading one get different rules than agents reading the other",
        "move what only CLAUDE.md holds into AGENTS.md (`diff AGENTS.md CLAUDE.md`), then `git rm CLAUDE.md`",
    )


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
        return ctx.not_a_repository()
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


def _current_branch(ctx: Context) -> str | None:
    """The branch of the worktree this run is in, when it is a linked worktree (not the main checkout); None otherwise."""
    git_dir = (ctx.git("rev-parse", "--path-format=absolute", "--git-dir") or "").strip()
    common = (ctx.git("rev-parse", "--path-format=absolute", "--git-common-dir") or "").strip()
    if not git_dir or git_dir == common:
        return None
    branch = (ctx.git("rev-parse", "--abbrev-ref", "HEAD") or "").strip()
    return branch if branch and branch != "HEAD" else None


def _merge_base_ref(ctx: Context) -> str:
    """What worktrees merge into: `origin/main` when it exists (a clone's local `main` goes stale beside worktrees), else `main`."""
    return "origin/main" if ctx.git("rev-parse", "--verify", "-q", "refs/remotes/origin/main") else "main"


def _stale(ctx: Context, branches: list[str]) -> list[str]:
    """Each branch with work unmerged, or main commits missing, past the limit, as a line saying how long."""
    limit = time.time() - float(str(ctx.settings.get("worktree-sync-hours", _SYNC_HOURS))) * 3600
    stale: list[str] = []
    base = _merge_base_ref(ctx)
    for branch in branches:
        unmerged = _oldest(ctx, f"{base}..{branch}")
        missing = _oldest(ctx, f"{branch}..{base}")
        if unmerged is not None and unmerged < limit:
            stale.append(f"{branch}: work unmerged since {_ago(unmerged)}")
        if missing is not None and missing < limit:
            stale.append(f"{branch}: behind main since {_ago(missing)}")
    return stale


@check(
    "agents.worktrees-in-sync",
    "the worktree this agent works in merges into main and takes main's changes within a day",
    version=2,
    layer="agent",
)
def worktrees_in_sync(ctx: Context) -> Finding:
    """The run is inside a linked worktree: its own branch is within a day of main, both ways.

    Why: a worktree that drifts for days turns its merge into conflict resolution and lets the agent build on a main that no
    longer exists (owner, 2026-10-11). Only this worktree: the agent cannot act on another session's (a2kay, 2026-11-21).
    """
    branch = _current_branch(ctx)
    if branch is None:
        return not_applicable("this is not a linked worktree (other sessions' worktrees: agents.other-worktrees, in the audit)")
    if stale := _stale(ctx, [branch]):
        return failing(
            "; ".join(stale),
            "land this worktree's work into main, or take main's changes into it (merge main), in this session",
            FixedBy.AGENT,
        )
    return passing(f"{branch} is within {_SYNC_HOURS}h of main both ways")


@check(
    "agents.other-worktrees",
    "every other session's worktree merges into main and takes main's changes within a day",
    audit_only=True,
    layer="agent",
)
def other_worktrees(ctx: Context) -> Finding:
    """Audit-only: this clone's linked worktrees but this run's own. Fails on unmerged work or missing main commits older than a day.

    The list is the owner's to act on: an agent cannot, and must not reach into a session that is not its own.
    """
    own = _current_branch(ctx)
    branches = [b for b in _branches(ctx) if b != own]
    if not branches:
        return not_applicable("no other linked worktrees")
    if stale := _stale(ctx, branches):
        # Another session works in each of these worktrees: whoever audits must not reach into them
        # (live run #7: the audit told an agent to rebase another session's worktree).
        return failing(
            "; ".join(stale),
            "each named worktree belongs to a session; ask the one working there to land its work into main or take "
            "main's changes, and remove worktrees whose work is done",
            FixedBy.OWNER,
        )
    return passing(f"{len(branches)} other worktrees, each within {_SYNC_HOURS}h of main both ways")


def _ago(stamp: int) -> str:
    return f"{(time.time() - stamp) / 3600:.0f}h ago"
