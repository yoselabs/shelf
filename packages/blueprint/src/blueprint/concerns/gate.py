"""Register gate checkpoints in their evaluation and report order."""

from __future__ import annotations

from blueprint.concerns import gate_ci, gate_clone, gate_command, gate_git, gate_guards, gate_hooks, gate_lfs
from blueprint.model import check

check("gate.one-command", "`just check` exists and every recipe it names resolves")(gate_command.one_command)
check("gate.runner", "the gate runner is just: a justfile holds the gate, not a Makefile")(gate_command.runner)
check("gate.ci", "CI runs the gate command; every action is pinned to a commit SHA; permissions are declared")(gate_ci.ci)
check("gate.ci-no-manifest-edit", "no CI step before the gate rewrites a dependency manifest or lockfile")(gate_ci.ci_no_manifest_edit)
check(
    "gate.hooks-recipe",
    "prek owns the git hooks through .pre-commit-config.yaml, bd's hooks run from it, pre-push runs the gate",
    version=3,
)(gate_hooks.hooks_recipe)
check("gate.hooks-installed", "the installed git hooks are prek's, in .git/hooks, with no bd block injected", version=2, audit_only=True)(
    gate_hooks.hooks_installed
)
check(
    "gate.runs-blueprint",
    "`just check` runs blueprint's per-commit checkpoints (`just blueprint`)",
    version=2,
)(gate_guards.runs_blueprint)
check("gate.guards-have-red-tests", "every repo-local script `just check` runs has a test that names it", version=2)(
    gate_guards.guards_have_red_tests
)
check("gate.clean-clone", "a fresh clone passes `just check` within its recorded budget", audit_only=True)(gate_clone.clean_clone)
check("gate.checkers-wired", "every check/lint script under tools/ or scripts/ is run by `just check`")(gate_guards.checkers_wired)
check("gate.default-branch", "the default branch is `main`", audit_only=True)(gate_git.default_branch)
check("gate.git-remote", "an `origin` remote exists, so pushes, CI and bd's Dolt sync have somewhere to go", audit_only=True)(
    gate_git.git_remote
)
check("gate.ci-green", "CI is green on the default branch's latest commit", audit_only=True)(gate_ci.ci_green)
check("gate.lfs-binaries", "in a repo that uses LFS, every binary blob in git is an LFS pointer")(gate_lfs.lfs_binaries)
check("gate.git-config-clean", "this clone's own git config sets neither core.worktree nor core.bare", audit_only=True)(
    gate_git.git_config_clean
)
check("gate.lfs-installed", "in a repo that uses LFS, this clone has git-lfs and its filter installed", audit_only=True)(
    gate_lfs.lfs_installed
)
