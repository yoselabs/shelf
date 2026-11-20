"""Gate no-ci: no repository holds GitHub Actions configuration (ADR 0027)."""

from __future__ import annotations

from blueprint.model import Context, Finding, FixedBy, failing, passing

_SUFFIXES = {".yml", ".yaml"}


def actions_files(ctx: Context) -> list[str]:
    """Workflows under `.github/workflows` and composite actions (`action.yml`) under `.github/actions`, as repo-relative paths."""
    found: list[str] = []
    for folder, pick in ((".github/workflows", "*"), (".github/actions", "**/action.*")):
        root = ctx.path(folder)
        if root.is_dir():
            found += [p.relative_to(ctx.repo).as_posix() for p in sorted(root.glob(pick)) if p.is_file() and p.suffix in _SUFFIXES]
    return sorted(found)


def no_ci(ctx: Context) -> Finding:
    """GitHub Actions: no repository has CI; the gate runs locally (hooks and `just check`)."""
    files = actions_files(ctx)
    if not files:
        return passing("no .github/workflows or .github/actions configuration")
    return failing(
        f"GitHub Actions configuration: {', '.join(files)}",
        "delete these files: the gate runs locally (pre-push hook, `just check`), never in CI. A duty a workflow carried that is not "
        "CI (image publish, deploy, a scheduled eval) moves to a local command or waits for an owner decision; "
        "never keep the workflow to hold it",
        FixedBy.OWNER,
    )
