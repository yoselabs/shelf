"""Gate audit leftovers: the audit writes nothing tracked, so a tracked baseline or report is stale (ADR 0018)."""

from __future__ import annotations

from blueprint.model import Context, Finding, FixedBy, failing, passing

_DIR = "docs/blueprint"
BASELINE = f"{_DIR}/checkpoints.txt"


def audit_leftovers(ctx: Context) -> Finding:
    """`git ls-files docs/blueprint` lists no `checkpoints.txt` and no Markdown report (a file whose first line is `# Blueprint`)."""
    listed = ctx.git("ls-files", "-z", "--", _DIR)
    if listed is None:
        return ctx.not_a_repository()
    tracked = [p for p in listed.split("\0") if p]
    stale = [p for p in tracked if p == BASELINE or (p.count("/") == _DIR.count("/") + 1 and p.endswith(".md") and _is_report(ctx, p))]
    if not stale:
        return passing(f"{_DIR} holds no tracked baseline or audit report")
    return failing(
        f"tracked audit leftovers (the audit writes nothing tracked any more): {', '.join(stale)}",
        f"git rm {' '.join(stale)}; `blueprint check --write` puts reports in the ignored .blueprint/reports/",
        FixedBy.AUTO,
    )


def _is_report(ctx: Context, rel: str) -> bool:
    return (ctx.read(rel) or "").startswith("# Blueprint")
