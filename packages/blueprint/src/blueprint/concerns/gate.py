"""Register gate checkpoints in their evaluation and report order."""

from __future__ import annotations

from blueprint.concerns import gate_clone, gate_command, gate_git, gate_guards, gate_hooks, gate_inputs, gate_lfs, gate_no_ci
from blueprint.model import check

check("gate.one-command", "`just check` exists and every recipe it names resolves")(gate_command.one_command)
check("gate.runner", "the gate runner is just: a justfile holds the gate, not a Makefile")(gate_command.runner)
check("gate.no-ci", "the repo holds no GitHub Actions configuration (no repository has CI, ADR 0027)")(gate_no_ci.no_ci)
check("gate.step-inputs", "every step `check` runs declares the files it reads in gate-inputs.toml, so an unaffected commit does no work")(
    gate_inputs.step_inputs
)
check(
    "gate.hooks-recipe",
    "prek owns the git hooks through .pre-commit-config.yaml and pre-push runs the gate",
    version=4,
)(gate_hooks.hooks_recipe)
check("gate.hooks-installed", "the installed git hooks are prek's, in .git/hooks", version=3, audit_only=True)(gate_hooks.hooks_installed)
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
check("gate.superseded-scripts", "no gate script the shelf now ships as a package is copied into tools/ or scripts/")(
    gate_guards.superseded_scripts
)
check("gate.default-branch", "the default branch is `main`", audit_only=True)(gate_git.default_branch)
check("gate.git-remote", "an `origin` remote exists, so pushes and bd's Dolt sync have somewhere to go", audit_only=True)(
    gate_git.git_remote
)
check("gate.lfs-binaries", "in a repo that uses LFS, every binary blob in git is an LFS pointer")(gate_lfs.lfs_binaries)
check("gate.git-config-clean", "this clone's own git config sets neither core.worktree nor core.bare", audit_only=True)(
    gate_git.git_config_clean
)
check("gate.lfs-installed", "in a repo that uses LFS, this clone has git-lfs and its filter installed", audit_only=True)(
    gate_lfs.lfs_installed
)
