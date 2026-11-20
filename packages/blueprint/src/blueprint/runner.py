"""Select the checks a repo's profile calls for and run them all in this one process."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from datetime import date
from typing import TYPE_CHECKING

from blueprint import concerns
from blueprint.concerns import gate_git
from blueprint.model import REGISTRY, Check, Context, Finding, FixedBy, Profile, Sub, Verdict, not_checked
from blueprint.profile import DETECTION, Override, State, detect, load_state

if TYPE_CHECKING:
    from pathlib import Path

concerns.load()


@dataclass(frozen=True)
class Row:
    """One checkpoint's line in a report (design D18)."""

    id: str
    concern: str
    statement: str
    verdict: Verdict
    set_up: bool | None
    working: bool | None
    evidence: str
    remediation: str
    fixed_by: FixedBy
    blueprint_gap: bool = False
    layer: str = "generic"
    version: int = 1
    # Not in the set the repo's last audit judged: reported, never failing the gate, until the next
    # audit takes it in. A shelf change must not turn every consumer's pre-push red mid-task.
    new: bool = False

    @property
    def key(self) -> str:
        """`id@version`, the line the audit record keeps."""
        return f"{self.id}@{self.version}"


@dataclass(frozen=True)
class Run:
    """A whole run: the profile it judged, the checkpoint-set hash, every row."""

    profile: Profile
    set_hash: str
    rows: tuple[Row, ...]
    problems: tuple[str, ...]
    # Audit-only checkpoints that apply but did not run (no `--audit`): a summary that hides them
    # shows fewer failures than the audit's README holds.
    skipped_audit: int = 0
    # Every [[override]] the repo records, scoped or not: each report lists them first.
    overrides: tuple[Override, ...] = ()
    # Old shapes still read, each with the text that replaces it: reported, never failing.
    notices: tuple[str, ...] = ()

    @property
    def exit_code(self) -> int:
        """1 when anything fails or is not set up; 2 when nothing fails but something went unchecked.

        A row the blueprint itself cannot judge yet (`blueprint_gap`) counts for neither: it is the
        shelf's gap, filed there, not the repo's.
        """
        verdicts = {r.verdict for r in self.rows if not r.blueprint_gap and not r.new}
        if verdicts & {Verdict.FAILING, Verdict.NOT_SET_UP} or self.problems:
            return 1
        return 2 if Verdict.NOT_CHECKED in verdicts else 0


# An override whose expiry is this near, or past, is named in every run's output (never silent).
EXPIRY_NOTICE_DAYS = 14


def expiry_notices(overrides: tuple[Override, ...], today: date, days: int = EXPIRY_NOTICE_DAYS) -> tuple[str, ...]:
    """One notice per override that expired or expires within `days`. Dated, not counted down, so a report holding it stays still."""
    out = []
    for o in overrides:
        if o.expires is None:
            continue
        scope = f" (scope `{o.scope}`)" if o.scope else ""
        if o.expires < today:
            out.append(f"override `{o.id}`{scope} expired {o.expires.isoformat()}: it excuses nothing now; renew it or fix the checkpoint")
        elif (o.expires - today).days <= days:
            out.append(f"override `{o.id}`{scope} expires {o.expires.isoformat()} (within {days} days): renew it or fix the checkpoint")
    return tuple(out)


_GLOB = re.compile(r"[*?\[]")


def scoped_dead_notices(ctx: Context, row_ids: set[str]) -> tuple[str, ...]:
    """A scoped override that excused nothing: its check ran and no offender matched it, or its `detection` path is gone."""
    out = []
    for o in ctx.overrides:
        if not o.scope or o.problem(ctx.today or date.today()) is not None:  # noqa: DTZ011 -- a calendar date in the owner's zone
            continue
        if o.id == DETECTION:
            path = o.scope.rsplit(":", 1)[0] if re.search(r":\d+$", o.scope) else o.scope
            gone = not _GLOB.search(path) and not ctx.path(path.rstrip("/")).exists()
        else:
            gone = o.id in row_ids and (o.id, o.scope) not in ctx.used_overrides
        if gone:
            out.append(
                f"override `{o.id}` scope `{o.scope}` excuses nothing: no offender matches it; delete it from docs/blueprint/blueprint.toml"
            )
    return tuple(out)


def orphan_override_notices(overrides: tuple[Override, ...], row_ids: set[str], skipped_ids: set[str]) -> tuple[str, ...]:
    """An override whose checkpoint is not among the run's rows: renamed, removed, or a stack the repo no longer has."""
    return tuple(
        f"override `{o.id}` names no checkpoint this repo runs: renamed, removed or not applicable; delete it"
        for o in {o.id: o for o in overrides}.values()
        if o.id != DETECTION and o.id not in row_ids and o.id not in skipped_ids
    )


ACCEPTED = "docs/blueprint/checkpoints.txt"


def _accepted(repo: Path) -> set[str] | None:
    """The `id@version` lines the last audit wrote; None before the first audit, so all is enforced.

    An audit from before the record existed (a README, no record) counts as an empty record: every
    row it did not see passing is new, so consumers audited earlier are not turned red by an upgrade.
    """
    path = repo / ACCEPTED
    if path.is_file():
        return set(path.read_text().split())
    return set() if (repo / ACCEPTED).with_name("README.md").is_file() else None


def active(profile: Profile, concern: str | None = None) -> list[Check]:
    """The registered checks that apply to `profile`, in registry order."""
    return [c for c in REGISTRY if c.applies(profile) and (concern is None or c.concern == concern)]


def set_hash(checks: list[Check]) -> str:
    """Identity of the checkpoint set: sorted ids with each check's version."""
    return hashlib.sha256("\n".join(sorted(f"{c.id}@{c.version}" for c in checks)).encode()).hexdigest()[:12]


def _refused(finding: Finding) -> Finding:
    if not finding.evidence.strip():
        return not_checked("the check returned no evidence, so its verdict is refused")
    return finding


def _judge(chk: Check, ctx: Context) -> list[Sub]:
    try:
        result = chk.run(ctx)
    except Exception as exc:  # noqa: BLE001 -- one broken check must not hide the others' verdicts
        return [Sub(chk.concern, chk.id, chk.statement, not_checked(f"the check itself crashed: {type(exc).__name__}: {exc}"))]
    if isinstance(result, Finding):
        return [Sub(chk.concern, chk.id, chk.statement, _refused(result))]
    return [Sub(s.concern, s.id, s.statement, _refused(s.finding)) for s in result]


def _row(chk: Check, sub: Sub, state: State, today: date, dead: list[str]) -> Row:
    finding = sub.finding
    verdict, evidence = finding.verdict, finding.evidence
    # A scoped override acts inside its check (Context.excused); only an unscoped one overrides the whole row.
    override = next((o for o in state.overrides if o.id == sub.id and not o.scope), None)
    if override is not None and verdict in {Verdict.PASSING, Verdict.NOT_APPLICABLE} and override.problem(today) is None:
        dead.append(f"override `{override.id}` is dead: its checkpoint passes without it; delete it from docs/blueprint/blueprint.toml")
    if override is not None and verdict is not Verdict.PASSING:
        problem = override.problem(today)
        if problem is None:
            verdict = Verdict.PASSING
            kind = f" {override.code}" if override.code else ""
            evidence = f"override{kind} {override.lasts}, decided by {override.decided_by}: {override.reason} (saw: {evidence})"
        else:
            evidence = f"{evidence}; {problem}"
    return Row(
        sub.id,
        sub.concern,
        sub.statement,
        verdict,
        finding.set_up,
        finding.working,
        evidence,
        finding.remediation,
        finding.fixed_by,
        finding.blueprint_gap,
        chk.layer,
        chk.version,
    )


def _branch_aware(row: Row, branches: dict[str, list[str]]) -> Row:
    """An unmerged branch holding gate files makes the gate rows' fix the owner's call (merge it, or remediate main)."""
    if row.id not in gate_git.BRANCH_AWARE or row.verdict not in {Verdict.FAILING, Verdict.NOT_SET_UP}:
        return row
    evidence, remediation = gate_git.branch_note(row.evidence, row.remediation, branches)
    return replace(row, evidence=evidence, remediation=remediation, fixed_by=FixedBy.OWNER)


def run(
    repo: Path, *, concern: str | None = None, audit: bool = False, today: date | None = None, env: dict[str, str] | None = None
) -> Run:
    """Run every applicable check on `repo`; the audit-only ones only when `audit`."""
    repo = repo.resolve()
    today = today or date.today()  # noqa: DTZ011 -- override expiry is a calendar date in the owner's zone
    state = load_state(repo, today)
    profile = detect(repo, state)
    ctx = Context(repo=repo, profile=profile, settings=state.settings, overrides=state.overrides, today=today)
    if env is not None:
        ctx.env = env
    checks = active(profile, concern)
    dead: list[str] = []
    rows = tuple(_row(c, sub, state, today, dead) for c in checks if audit or not c.audit_only for sub in _judge(c, ctx))
    accepted = _accepted(repo)
    if accepted is not None:
        rows = tuple(replace(r, new=True) if r.key not in accepted and r.verdict is not Verdict.PASSING else r for r in rows)
    if audit and (branches := gate_git.unmerged_gate_branches(ctx)):
        rows = tuple(_branch_aware(r, branches) for r in rows)
    skipped = 0 if audit else sum(c.audit_only for c in checks)
    # Only a whole run knows which ids exist: a one-concern run would call every other concern's override an orphan.
    orphans = (
        orphan_override_notices(state.overrides, {r.id for r in rows}, {c.id for c in checks if c.audit_only and not audit})
        if concern is None
        else ()
    )
    return Run(
        profile=profile,
        set_hash=set_hash(active(profile)),
        rows=rows,
        problems=state.problems,
        skipped_audit=skipped,
        overrides=state.overrides,
        notices=(
            *state.notices,
            *ctx.notices,
            *expiry_notices(state.overrides, today),
            *dead,
            *scoped_dead_notices(ctx, {r.id for r in rows}),
            *orphans,
        ),
    )
