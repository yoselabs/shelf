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
    found = actions_files(ctx)
    files = [f for f in found if ctx.excused("gate.no-ci", f) is None]
    if not found:
        return passing("no .github/workflows or .github/actions configuration")
    if not files:
        return passing(f'{len(found)} GitHub Actions file(s), each excused by an [[override]] id = "gate.no-ci" with a reason')
    return failing(
        f"GitHub Actions configuration: {', '.join(files)}",
        "delete these files: the gate runs locally (pre-push hook, `just check`), never in CI. A duty a workflow carried that is not "
        "CI (image publish, deploy, a scheduled eval) moves to a local command or waits for an owner decision; "
        "never keep the workflow to hold it. A repo that needs CI (a deploy, an image build) says so with an "
        '[[override]] id = "gate.no-ci", scope = "<workflow path>", a reason and an end date, in docs/blueprint/blueprint.toml',
        FixedBy.OWNER,
    )
