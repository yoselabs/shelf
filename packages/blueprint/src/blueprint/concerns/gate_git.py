"""Gate git: owning domain checks and evidence."""

from __future__ import annotations

from fnmatch import fnmatch

from blueprint.model import (
    Context,
    Finding,
    FixedBy,
    failing,
    not_applicable,
    not_checked,
    not_set_up,
    passing,
)


def default_branch(ctx: Context) -> Finding:
    """origin/HEAD when there is a remote, else `main` if it exists, else the branch checked out."""
    if ctx.git("rev-parse", "--git-dir") is None:
        return ctx.not_a_repository()
    name = (ctx.git("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD") or "").strip().removeprefix("refs/remotes/origin/")
    if not name and ctx.git("show-ref", "--verify", "--quiet", "refs/heads/main") is not None:
        name = "main"
    name = name or (ctx.git("symbolic-ref", "--quiet", "--short", "HEAD") or "").strip()
    if not name:
        return not_checked("detached HEAD, no origin/HEAD and no main branch: the default branch cannot be told")
    if name != "main":
        return failing(
            f"the default branch is {name}, the shelf and its tools assume main",
            f"git branch -m {name} main; with a remote: git push -u origin main, make main the host's default branch, delete {name} there",
        )
    return passing("the default branch is main")


def git_remote(ctx: Context) -> Finding:
    """`git remote` lists origin; none at all is not set up yet, others without origin is a rename."""
    listed = ctx.git("remote")
    if listed is None:
        return ctx.not_a_repository()
    remotes = listed.split()
    if "origin" in remotes:
        return passing("origin: " + (ctx.git("remote", "get-url", "origin") or "").strip())
    if remotes:
        return failing(f"remotes {', '.join(remotes)}, none called origin", f"git remote rename {remotes[0]} origin")
    return not_set_up(
        "no git remote",
        "git remote add origin <url> and push; a repo kept local on purpose is an override of gate.git-remote with a reason and an adr",
    )


def git_config_clean(ctx: Context) -> Finding:
    """A leaked GIT_WORK_TREE once wrote core.worktree into .git/config (homelab, lifesim): every worktree then ran git against one tree."""
    if not ctx.path(".git").is_dir():
        return not_applicable("not the main checkout of a non-bare clone (a linked worktree or no git repository)")
    worktree = (ctx.git("config", "--local", "--get", "core.worktree") or "").strip()
    bare = (ctx.git("config", "--local", "--get", "core.bare") or "").strip().lower()
    if worktree:
        return failing(
            f"core.worktree is set to {worktree!r} in .git/config: git answers for that tree, not this one",
            "git config --unset core.worktree",
            FixedBy.AUTO,
        )
    if bare in {"true", "yes", "on", "1"}:
        return failing("core.bare is true in a clone that has a working tree", "git config core.bare false", FixedBy.AUTO)
    return passing("no core.worktree and no core.bare in .git/config")


# The files that make a gate. A remote branch holding one of them may already carry the gate main lacks.
_GATE_FILES = ("justfile", "Makefile", ".pre-commit-config.yaml", "lefthook.yml", "lefthook.yaml", ".github/workflows/*")
# The rows that tell an agent to build or repair a gate: where an unmerged branch holding one changes who decides.
BRANCH_AWARE = frozenset(
    {
        "gate.one-command",
        "gate.runner",
        "gate.ci",
        "gate.ci-no-manifest-edit",
        "gate.hooks-recipe",
        "gate.runs-blueprint",
        "gate.clean-clone",
    }
)


def unmerged_gate_branches(ctx: Context) -> dict[str, list[str]]:
    """Remote-tracking branches ahead of the default branch -> the gate files they change there.

    Local refs only (no fetch), and nothing is run against a branch: the owner judges it.
    """
    head = (ctx.git("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD") or "").strip().removeprefix("refs/remotes/")
    base = head or "origin/main"
    if ctx.git("rev-parse", "--verify", "--quiet", base) is None:
        return {}
    refs = (ctx.git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin") or "").split()
    found: dict[str, list[str]] = {}
    for ref in refs:
        if ref in {base, "origin", "origin/HEAD"}:
            continue
        changed = (ctx.git("diff", "--name-only", f"{base}...{ref}") or "").splitlines()
        if files := [f for f in changed if any(fnmatch(f, pattern) for pattern in _GATE_FILES)]:
            found[ref] = files
    return found


def branch_note(evidence: str, remediation: str, branches: dict[str, list[str]]) -> tuple[str, str]:
    """A not-passing gate row's evidence and remediation, naming the branches that hold gate files and handing the decision to the owner."""
    held = "; ".join(f"{ref} changes {', '.join(files)}" for ref, files in branches.items())
    return (
        f"{evidence}; unmerged remote branch(es) hold gate files: {held}",
        f"do not build a parallel gate: the owner decides whether to merge that branch or remediate on main "
        f"(the branch is not judged here). Without the branch: {remediation}".rstrip(": "),
    )
